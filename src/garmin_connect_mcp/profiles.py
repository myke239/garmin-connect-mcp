"""Fixed discovery profiles; removing a tool also removes its callable handler."""
import os

READS={'connection_status','list_activities','get_activity','get_activity_splits','get_activity_samples','get_strength_sets','get_training_summary'}
RECOVERY={'get_garmin_recovery','get_session_with_context','list_garmin_lifestyle_fields','get_garmin_lifestyle_entries'}
RECOVERY |= {'get_garmin_coaching_day','analyze_garmin_daily_recovery','compare_garmin_workout_outcomes','analyze_garmin_lifestyle_association'}
RECOVERY.add('assess_garmin_strength_session')
RECOVERY.add('get_garmin_coaching_guide')
RECOVERY |= {'get_garmin_lifestyle_mutation_target','get_garmin_lifestyle_auto_logging'}
PLANNING={'list_workout_templates','get_workout_template','list_scheduled_workouts','list_garmin_devices','list_garmin_activity_types','find_garmin_exercises','get_garmin_workout_schema','list_garmin_workout_sports','build_garmin_workout','get_garmin_activity_schema','build_garmin_manual_activity','build_garmin_strength_step','build_garmin_yoga_step','build_garmin_strength_workout','build_garmin_running_workout','build_garmin_swim_workout','clone_garmin_workout','get_garmin_workout_mutation_target'}
PERFORMANCE={'list_archived_activities','get_archived_activity_analysis','compare_garmin_intervals','archive_garmin_activity'}


def apply(server,profile=None):
    selected=profile or os.environ.get('GARMIN_MCP_TOOL_PROFILE','all')
    if selected=='all': return
    if selected not in {'read-only','recovery','planning','performance'}:
        raise ValueError('Unknown tool profile; choose all/read-only/recovery/planning/performance')
    available=set(server._tool_manager._tools)
    if selected=='read-only':
        allowed={name for name in available if server._tool_manager._tools[name].annotations.readOnlyHint}
    elif selected=='recovery': allowed=READS|RECOVERY
    elif selected=='performance': allowed=READS|RECOVERY|PERFORMANCE
    else: allowed=READS|PLANNING|{'get_garmin_lifestyle_mutation_target','get_garmin_lifestyle_auto_logging'}|{name for name in available if name.startswith('commit_garmin_') or name in {'prepare_garmin_write','get_garmin_write_schema','get_garmin_write_status'}}
    for name in available-allowed: server.remove_tool(name)
