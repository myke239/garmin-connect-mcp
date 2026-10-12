"""Opt-in live tests. Run only with explicit account-mutation authorization.

Tracks test resources in encrypted local state and never changes pre-existing
workouts/activities/health measurements. --cleanup can be rerun after interruption.
"""
import argparse
import base64
import copy
import json
import sys
import uuid
from datetime import datetime,timezone
from pathlib import Path

from garmin_connect_mcp.auth import TokenStore,restore_session
from garmin_connect_mcp.runtime import session_lock,error_code
from garmin_connect_mcp.writes import WriteService

from audit_fixtures import fit_activity,gpx_activity,tcx_activity

ROOT=Path(__file__).resolve().parents[1]
DAY="2000-01-02"


class Audit:
    def __init__(self):
        self.store=TokenStore(ROOT/"work"/"live-write-audit")
        self.account=TokenStore()
        self.writes=WriteService(self.account.directory)
        self.state=json.loads(self.store.load()) if self.store.exists() else {
            "run_id":uuid.uuid4().hex[:12],"checks":{},"workouts":[],"activities":[],
            "scheduled":[],"health_baseline":{},"hydration_added":False,"cleanup":{}}
        self.prefix="MCP AUDIT "+self.state["run_id"]

    def save(self): self.store.save(json.dumps(self.state))

    def read(self,method,*args,**kwargs):
        with session_lock(self.account):
            client=restore_session(self.account)
            try: return getattr(client,method)(*args,**kwargs)
            finally: self.account.save(client.client.dumps())

    def write(self,label,operation,parameters):
        if label in self.state["checks"]:
            print(label,"already recorded; not retried",flush=True)
            return self.state["checks"][label].get("result")
        draft=self.writes.prepare(operation,parameters,"audit-"+self.state["run_id"]+"-"+label)
        self.state["checks"][label]={"operation":operation,"draft_id":draft["draft_id"],"status":"attempted"}
        self.save()
        try:
            result=self.writes.commit(draft["draft_id"])
            self.state["checks"][label]["result"]=result
            self.state["checks"][label]["status"]=result["status"]
            print(label,result["status"],result.get("error",{}),flush=True)
            return result
        except Exception as error:
            self.state["checks"][label]["status"]="unknown"
            self.state["checks"][label]["error_code"]=error_code(error)
            print(label,"unconfirmed",error_code(error),flush=True)
            return None
        finally: self.save()

    def identifier(self,result,field):
        if not result or result["status"]!="completed": return None
        values=result.get("result",{}).get(field,[])
        return values[0] if values else None

    def mark_verified(self,label,condition):
        self.state["checks"][label]["verified"]=bool(condition)
        self.save()
        print(label,"read verification",bool(condition),flush=True)

    def capture_baseline(self):
        if self.state["health_baseline"]: return
        weight=self.read("get_body_composition",DAY,DAY)
        blood=self.read("get_blood_pressure",DAY,DAY)
        hydration=self.read("get_hydration_data",DAY)
        self.state["health_baseline"]={"weight":weight,"blood_pressure":blood,"hydration":hydration}
        self.state["baseline_activity_ids"]=[str(v["activityId"]) for v in self.read("get_activities_by_date",DAY,DAY)]
        self.save()

    def run(self):
        self.writes.require_enabled()
        self.capture_baseline()
        template=json.loads((ROOT/"plugins/garmin-connect/skills/create-schedule-workouts/references/easy-distance-run.json").read_text())
        template["workoutName"]=self.prefix+" running"
        template["workoutSegments"][0]["workoutSteps"][0]["endConditionValue"]=100
        result=self.write("create_workout","create_workout",{"workout_json":template})
        identity=self.identifier(result,"workoutId")
        if identity:
            if identity not in self.state["workouts"]: self.state["workouts"].append(identity); self.save()
            original=self.read("get_workout_by_id",identity)
            self.mark_verified("create_workout",original.get("workoutName")==template["workoutName"])
            updated=copy.deepcopy(template); updated["workoutName"]=self.prefix+" updated"
            self.write("update_workout","update_workout",{"workout_id":identity,"workout_json":updated})
            self.mark_verified("update_workout",self.read("get_workout_by_id",identity).get("workoutName")==updated["workoutName"])
            result=self.write("schedule_workout","schedule_workout",{"workout_id":identity,"date_str":"2026-10-28"})
            if result and result["status"]=="completed":
                rows=self.read("get_scheduled_workouts",2026,10)["calendarItems"]
                candidates=[r for r in rows if r.get("itemType")=="workout" and r.get("title")==updated["workoutName"] and str(r.get("date","")).startswith("2026-10-28")]
                self.mark_verified("schedule_workout",len(candidates)==1)
                for row in candidates:
                    entry=str(row["id"])
                    if entry not in self.state["scheduled"]: self.state["scheduled"].append(entry); self.save()
                    removed=self.write("unschedule_workout","unschedule_workout",{"scheduled_workout_id":entry})
                    remaining=self.read("get_scheduled_workouts",2026,10)["calendarItems"]
                    self.mark_verified("unschedule_workout",not any(str(r.get("id"))==entry and r.get("itemType")=="workout" for r in remaining))
            devices=self.read("get_devices")
            device=next((v for v in devices if v.get("primary") and v.get("deviceId")),None)
            device=device or next((v for v in devices if v.get("deviceId")),None)
            if device:
                self.write("send_workout_to_device","send_workout_to_device",{"workout_id":identity,"device_id":str(device["deviceId"])})
                self.state["checks"]["send_workout_to_device"]["verification_limit"]="SDK queue response only; physical download cannot be verified here"
                self.save()

        batch=copy.deepcopy(template); batch["workoutName"]=self.prefix+" calendar"
        result=self.write("create_training_calendar","create_training_calendar",{"workouts":[{"date":"2026-10-29","workout":batch}]})
        if result:
            for step in result.get("steps",[]):
                wid=step["created_workout_id"]
                if wid not in self.state["workouts"]: self.state["workouts"].append(wid); self.save()
            rows=self.read("get_scheduled_workouts",2026,10)["calendarItems"]
            candidates=[r for r in rows if r.get("itemType")=="workout" and r.get("title")==batch["workoutName"]]
            for row in candidates:
                if str(row["id"]) not in self.state["scheduled"]: self.state["scheduled"].append(str(row["id"])); self.save()
            self.mark_verified("create_training_calendar",result["status"]=="completed" and len(candidates)==1)

        from zoneinfo import ZoneInfo
        local_day=datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
        result=self.write("create_manual_activity","create_manual_activity",{"start_datetime":local_day+"T00:00:00.000","time_zone":"America/Los_Angeles",
            "type_key":"walking","distance_km":0.1,"duration_min":1,"activity_name":self.prefix+" manual"})
        aid=self.identifier(result,"activityId")
        if aid:
            if aid not in self.state["activities"]: self.state["activities"].append(aid); self.save()
            raw=self.read("get_activity",aid)
            self.mark_verified("create_manual_activity",raw.get("activityName")==self.prefix+" manual")
            self.write("set_activity_name","set_activity_name",{"activity_id":aid,"title":self.prefix+" renamed"})
            self.mark_verified("set_activity_name",self.read("get_activity",aid).get("activityName")==self.prefix+" renamed")
            self.write("set_activity_description","set_activity_description",{"activity_id":aid,"description":"Explicitly synthetic integration audit; delete after testing."})
            self.mark_verified("set_activity_description",bool(self.read("get_activity",aid).get("description")))
            raw_sets=self.read("get_activity_exercise_sets",aid)
            replacement=copy.deepcopy(raw_sets); replacement["exerciseSets"]=[{"setType":"ACTIVE","repetitionCount":1,"duration":1,
                "weight":0,"exercises":[{"category":"PUSH_UP","name":None}]}]
            self.write("replace_strength_sets","replace_strength_sets",{"activity_id":aid,"payload":replacement})
            self.mark_verified("replace_strength_sets",bool(self.read("get_activity_exercise_sets",aid).get("exerciseSets")))
            types=self.read("get_activity_types")
            chosen=next(v for v in types if v.get("typeKey")=="walking")
            self.write("set_activity_type","set_activity_type",{"activity_id":aid,"type_id":chosen["typeId"],"type_key":chosen["typeKey"],"parent_type_id":chosen["parentTypeId"]})
            self.mark_verified("set_activity_type",self.read("get_activity",aid).get("activityTypeDTO",{}).get("typeKey")=="walking")

        for format,content in [("gpx",gpx_activity(self.prefix)),("tcx",tcx_activity(self.prefix)),("fit",fit_activity())]:
            result=self.write("upload_"+format,"upload_activity_file",{"format":format,"content_base64":base64.b64encode(content).decode()})
            if result:
                imported=result.get("result",{}).get("internalId",[]) or result.get("result",{}).get("activityId",[])
                for aid in imported:
                    if aid not in self.state["activities"]: self.state["activities"].append(aid); self.save()
                if not imported:
                    hour={"gpx":"10","tcx":"11","fit":"12"}[format]
                    rows=self.read("get_activities_by_date",DAY,DAY)
                    candidates=[v for v in rows if str(v["activityId"]) not in self.state.get("baseline_activity_ids",[])
                        and str(v.get("startTimeGMT","")).replace(" ","T").startswith(DAY+"T"+hour+":00:00")
                        and v.get("duration")==60 and round(v.get("distance",0)) in (100,111)]
                    if len(candidates)==1:
                        imported=[str(candidates[0]["activityId"])]
                        self.state["checks"]["upload_"+format]["reconciled_activity_id"]=imported[0]
                        if imported[0] not in self.state["activities"]:self.state["activities"].append(imported[0])
                        self.save()
                if imported: self.mark_verified("upload_"+format,bool(self.read("get_activity",imported[0])))

        baseline=self.state["health_baseline"]
        if not baseline["weight"].get("dateWeightList"):
            self.write("add_weight","add_weight",{"weight":70,"timestamp":DAY+"T13:00:00+00:00","unitKey":"kg"})
            self.mark_verified("add_weight",bool(self.read("get_body_composition",DAY,DAY).get("dateWeightList")))
            self.write("add_body_composition","add_body_composition",{"weight":71,"percent_fat":20,"timestamp":DAY+"T14:00:00+00:00"})
            self.mark_verified("add_body_composition",len(self.read("get_body_composition",DAY,DAY).get("dateWeightList",[]))>=2)
        else: print("Health weight tests skipped: audit date already has measurements",flush=True)
        if not baseline["blood_pressure"].get("measurementSummaries"):
            self.write("add_blood_pressure","add_blood_pressure",{"systolic":120,"diastolic":80,"pulse":60,"timestamp":DAY+"T15:00:00+00:00","notes":self.prefix+" synthetic"})
            self.mark_verified("add_blood_pressure",bool(self.read("get_blood_pressure",DAY,DAY).get("measurementSummaries")))
        else: print("Blood pressure skipped: audit date already has measurements",flush=True)
        if baseline["hydration"].get("valueInML") in (None,0):
            result=self.write("add_hydration","add_hydration",{"value_in_ml":250,"timestamp":DAY+"T16:00:00+00:00","cdate":DAY})
            if result and result["status"]=="completed": self.state["hydration_added"]=True; self.save()
            self.mark_verified("add_hydration",self.read("get_hydration_data",DAY).get("valueInML")==250)
        else: print("Hydration skipped: audit date already has data",flush=True)

    def cleanup(self):
        # Import responses can omit IDs. Reconcile only new records matching the
        # exact synthetic recording fingerprint, never the pre-test inventory.
        if any(label in self.state["checks"] for label in ("upload_gpx","upload_tcx","upload_fit")):
            rows=self.read("get_activities_by_date",DAY,DAY)
            for label,hour in (("upload_gpx","10"),("upload_tcx","11"),("upload_fit","12")):
                if label not in self.state["checks"]: continue
                candidates=[v for v in rows if str(v["activityId"]) not in self.state.get("baseline_activity_ids",[])
                    and str(v.get("startTimeGMT","")).replace(" ","T").startswith(DAY+"T"+hour+":00:00")
                    and v.get("duration")==60 and round(v.get("distance",0)) in (100,111)]
                if len(candidates)==1:
                    identity=str(candidates[0]["activityId"])
                    if identity not in self.state["activities"]: self.state["activities"].append(identity)
                    self.state["checks"][label]["verified"]=True
                    self.state["checks"][label]["reconciled_activity_id"]=identity
            self.save()
        for entry in self.state["scheduled"]:
            key="schedule-"+entry
            if self.state["cleanup"].get(key): continue
            try: self.read("unschedule_workout",entry); self.state["cleanup"][key]=True
            except Exception as error: self.state["cleanup"][key]=error_code(error)
            self.save()
        for kind,collection,method in [("workout","workouts","delete_workout"),("activity","activities","delete_activity")]:
            for identity in self.state[collection]:
                key=kind+"-"+identity
                if self.state["cleanup"].get(key) is True: continue
                try: self.read(method,identity); self.state["cleanup"][key]=True
                except Exception as error: self.state["cleanup"][key]=error_code(error)
                self.save()
        baseline=self.state["health_baseline"]
        if baseline and not baseline["weight"].get("dateWeightList"):
            rows=self.read("get_body_composition",DAY,DAY).get("dateWeightList",[])
            for row in rows:
                expected={int(datetime(2000,1,2,hour,tzinfo=timezone.utc).timestamp()*1000) for hour in (13,14)}
                if row.get("timestampGMT") not in expected or row.get("weight") not in (70000,71000,70,71):
                    continue  # Never delete an unexpected concurrent measurement.
                identity=row.get("samplePk") or row.get("weightPk")
                if identity:
                    self.read("delete_weigh_in",str(identity),DAY)
            self.state["cleanup"]["weight_empty"]=not self.read("get_body_composition",DAY,DAY).get("dateWeightList")
            self.save()
        if self.state["hydration_added"]:
            current=self.read("get_hydration_data",DAY).get("valueInML")
            if current==250:
                self.read("add_hydration_data",-250,DAY+"T16:00:00+00:00",DAY)
            self.state["cleanup"]["hydration_zero"]=self.read("get_hydration_data",DAY).get("valueInML") in (None,0)
            self.save()
        # Blood-pressure version keys are intentionally discovered from the live
        # response before deleting; no guessing IDs or touching an existing day.
        if baseline and not baseline["blood_pressure"].get("measurementSummaries"):
            raw=self.read("get_blood_pressure",DAY,DAY)
            def versions(value):
                if isinstance(value,dict):
                    if "version" in value and "systolic" in value: yield value["version"]
                    for child in value.values(): yield from versions(child)
                elif isinstance(value,list):
                    for child in value: yield from versions(child)
            for version in versions(raw): self.read("delete_blood_pressure",str(version),DAY)
            self.state["cleanup"]["blood_pressure_empty"]=not self.read("get_blood_pressure",DAY,DAY).get("measurementSummaries")
            self.save()
        print("Cleanup checks:",{k:v for k,v in self.state["cleanup"].items() if not k.startswith(("workout-","activity-","schedule-"))},flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",action="store_true",help="Explicitly run account mutations; requires prior owner authorization")
    parser.add_argument("--cleanup",action="store_true",help="Only clean up resources recorded by this audit")
    args=parser.parse_args()
    audit=Audit()
    if not args.run and not args.cleanup:
        print("No writes executed. Pass --run only with owner authorization.")
        return
    if args.run and audit.state["checks"]:
        print("This audit already has recorded attempts. Use --cleanup and inspect the evidence; no writes were retried.")
        return
    try:
        if args.run: audit.run()
    except Exception as error:
        print("Audit stopped safely:",error_code(error),flush=True)
        raise SystemExit(1) from None
    finally: audit.cleanup()


if __name__=="__main__": main()
