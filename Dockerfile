# Salvage in one container: two Anvil forks (Ethereum and Base), the airdrop contracts, the wallet set, and the web UI.
# Build:  docker build -t salvage .
# Run:    docker run --env-file .env -e SERVE_HOST=0.0.0.0 -p 8000:8000 salvage
# The forks need archive RPC upstreams (ETH_RPC_URL, BASE_RPC_URL); everything else is optional.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl git ca-certificates bash && rm -rf /var/lib/apt/lists/*

# Foundry: anvil for the forks, forge for the airdrop contract
ENV FOUNDRY_DIR=/root/.foundry
RUN curl -L https://foundry.paradigm.xyz | bash && /root/.foundry/bin/foundryup
ENV PATH="/root/.foundry/bin:${PATH}"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p logs data/runs && cd contracts && forge build

ENV SERVE_HOST=0.0.0.0 PORT=8000 FORK_RPC_URL=http://127.0.0.1:8545 BASE_FORK_RPC_URL=http://127.0.0.1:8546
EXPOSE 8000
CMD ["bash", "scripts/container_start.sh"]
