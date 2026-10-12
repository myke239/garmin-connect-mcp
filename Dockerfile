FROM python:3.13-slim
RUN useradd --create-home --uid 10001 garmin
WORKDIR /opt/garmin
COPY pyproject.toml README.md LICENSE NOTICE VERSION ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade 'pip>=26.2.1' && pip install --no-cache-dir '.[remote]' && rm -rf src
USER 10001:10001
ENV GARMIN_MCP_DATA_DIR=/home/garmin/.local/share/garmin-connect-mcp
VOLUME /home/garmin/.local/share/garmin-connect-mcp
ENTRYPOINT ["python", "-m", "garmin_connect_mcp.manage"]
CMD ["serve"]
