"""Verify a frozen binary via real MCP stdio and a private temporary data directory."""
import asyncio,os,sys,tempfile,json,base64
from pathlib import Path
from garmin_connect_mcp.auth import TokenStore
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

async def verify(executable):
    with tempfile.TemporaryDirectory() as directory:
        TokenStore(Path(directory)/'write-settings').save(json.dumps({'enabled':True}))
        environment={**os.environ,'GARMIN_MCP_DATA_DIR':directory,'GARMIN_MCP_TOOL_PROFILE':'all'}
        async with stdio_client(StdioServerParameters(command=executable,args=['serve'],env=environment)) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize()
                tools=await client.list_tools()
                assert len(tools.tools)==52
                value=await client.call_tool('connection_status',{})
                assert 'auth_required' in value.content[0].text
                schema=await client.call_tool('get_garmin_write_schema',{'operation':'delete_workout'})
                assert 'expected_content_sha256' in schema.content[0].text
                activity=await client.call_tool('get_activity',{'activity_id':'1'})
                assert 'AUTH_REQUIRED' in activity.content[0].text
                from audit_fixtures import fit_activity
                result=await client.call_tool('prepare_garmin_write',{'operation':'upload_activity_file',
                    'parameters':{'format':'fit','content_base64':base64.b64encode(fit_activity()).decode()},
                    'idempotency_key':'frozen-fit-codec-check'})
                value=json.loads(result.content[0].text)
                assert value.get('status')=='prepared' or value.get('error',{}).get('code')=='FIT_SUPPORT_REQUIRED',value
                print('FIT add-on: '+('verified' if value.get('status')=='prepared' else 'explicit local setup required'))
    print('PASS: frozen executable MCP handshake, 52 tools and guarded lifecycle contract')

if __name__=='__main__':asyncio.run(verify(sys.argv[1]))
