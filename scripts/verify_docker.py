"""Offline container MCP handshake using a disposable owner-only tmpfs."""
import asyncio,sys
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

async def verify(image):
    parameters=StdioServerParameters(command='docker',args=['run','--rm','-i','--network','none','--read-only',
        '--tmpfs','/home/garmin/.local/share/garmin-connect-mcp:uid=10001,gid=10001,mode=0700',image,'serve'])
    async with stdio_client(parameters) as (read,write):
        async with ClientSession(read,write) as client:
            await client.initialize()
            assert len((await client.list_tools()).tools)==54
            value=await client.call_tool('get_activity',{'activity_id':'1'})
            assert 'AUTH_REQUIRED' in value.content[0].text
    print('PASS: non-root read-only network-isolated Docker MCP and subprocess worker')

if __name__=='__main__':asyncio.run(verify(sys.argv[1]))
