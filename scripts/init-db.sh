#!/bin/bash
# Creates the databases + roles used by the full docker-compose stack.
# Mounted into the postgres container at /docker-entrypoint-initdb.d/
# so it runs once on first boot.

set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE ROLE assistant WITH LOGIN PASSWORD 'assistant';
    CREATE ROLE litellm   WITH LOGIN PASSWORD 'litellm';
    CREATE ROLE langfuse  WITH LOGIN PASSWORD 'langfuse';

    CREATE DATABASE assistant OWNER assistant;
    CREATE DATABASE litellm   OWNER litellm;
    CREATE DATABASE langfuse  OWNER langfuse;

    GRANT ALL PRIVILEGES ON DATABASE assistant TO assistant;
    GRANT ALL PRIVILEGES ON DATABASE litellm   TO litellm;
    GRANT ALL PRIVILEGES ON DATABASE langfuse  TO langfuse;
EOSQL
