FROM kalilinux/kali-rolling:latest

LABEL description="AI Agent Penetration Testing Environment with Comprehensive Automated Tools - Enhanced White-Box Scanning Capabilities"
LABEL whitebox.version="2.0"
LABEL whitebox.capabilities="SAST, DAST, SCA, Secret Detection, Code Quality, Multi-Language Support"

RUN apt-get update && \
    apt-get install -y kali-archive-keyring sudo && \
    apt-get update && \
    apt-get upgrade -y

RUN useradd -m -s /bin/bash pentester && \
    usermod -aG sudo pentester && \
    echo "pentester ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /home/pentester/configs \
             /home/pentester/wordlists \
             /home/pentester/output \
             /home/pentester/scripts \
             /home/pentester/tools \
             /app/runtime \
             /app/tools \
             /app/certs && \
    chown -R pentester:pentester /app/certs /home/pentester/tools

# =============================================================================
# BASE SYSTEM PACKAGES + WHITE-BOX SCANNING DEPENDENCIES
# =============================================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # Core utilities
    wget curl git vim nano unzip tar \
    apt-transport-https ca-certificates gnupg lsb-release \
    build-essential software-properties-common \
    gcc g++ libc6-dev pkg-config libpcap-dev libssl-dev \
    # Python ecosystem (for SAST tools)
    python3 python3-pip python3-dev python3-venv python3-setuptools \
    # Go ecosystem (for security tools)
    golang-go \
    # Network utilities
    net-tools dnsutils whois \
    jq parallel ripgrep grep fd-find \
    less man-db procps htop \
    iproute2 iputils-ping netcat-traditional \
    # Security scanning tools
    nmap ncat ndiff \
    sqlmap nuclei subfinder naabu ffuf \
    # Node.js ecosystem (for JS/TS analysis)
    nodejs npm pipx \
    # System capabilities
    libcap2-bin \
    gdb strace ltrace \
    tmux screen \
    # Browser dependencies
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libatspi2.0-0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 libasound2 \
    fonts-unifont fonts-noto-color-emoji fonts-freefont-ttf fonts-dejavu-core ttf-bitstream-vera \
    libnss3-tools \
    # =========================================================================
    # WHITE-BOX SCANNING DEPENDENCIES
    # =========================================================================
    # Java ecosystem (for Java/Kotlin analysis)
    default-jdk default-jre maven gradle \
    # Ruby ecosystem (for Ruby analysis)
    ruby ruby-dev \
    # PHP ecosystem (for PHP analysis)
    php php-cli php-xml php-mbstring php-curl composer \
    # .NET/C# ecosystem
    dotnet-sdk-8.0 || true \
    # Rust ecosystem (for Rust analysis)  
    rustc cargo \
    # Code analysis dependencies
    clang clang-tools llvm \
    # Additional utilities for code analysis
    tree file xxd hexdump \
    universal-ctags cscope \
    # XML/JSON processing
    xmlstarlet libxml2-utils \
    # Database clients for testing
    sqlite3 postgresql-client mysql-client || true

RUN setcap cap_net_raw,cap_net_admin,cap_net_bind_service+eip $(which nmap)

USER pentester
RUN openssl ecparam -name prime256v1 -genkey -noout -out /app/certs/ca.key && \
    openssl req -x509 -new -key /app/certs/ca.key \
    -out /app/certs/ca.crt \
    -days 3650 \
    -subj "/C=US/ST=CA/O=Security Testing/CN=Testing Root CA" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign" && \
    openssl pkcs12 -export \
    -out /app/certs/ca.p12 \
    -inkey /app/certs/ca.key \
    -in /app/certs/ca.crt \
    -passout pass:"" \
    -name "Testing Root CA" && \
    chmod 644 /app/certs/ca.crt && \
    chmod 600 /app/certs/ca.key && \
    chmod 600 /app/certs/ca.p12

USER root
RUN cp /app/certs/ca.crt /usr/local/share/ca-certificates/ca.crt && \
    update-ca-certificates

RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python3 - && \
    ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry && \
    chmod +x /usr/local/bin/poetry && \
    python3 -m venv /app/venv && \
    chown -R pentester:pentester /app/venv /opt/poetry

USER pentester
WORKDIR /tmp

# =============================================================================
# GO-BASED SECURITY TOOLS (Enhanced for White-Box Scanning)
# =============================================================================
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest && \
    go install -v github.com/projectdiscovery/katana/cmd/katana@latest && \
    go install -v github.com/projectdiscovery/cvemap/cmd/vulnx@latest && \
    go install -v github.com/jaeles-project/gospider@latest && \
    go install -v github.com/projectdiscovery/interactsh/cmd/interactsh-client@latest && \
    # WHITE-BOX: Static Analysis & Code Security Tools
    go install -v github.com/securego/gosec/v2/cmd/gosec@latest && \
    go install -v golang.org/x/vuln/cmd/govulncheck@latest && \
    go install -v github.com/golangci/golangci-lint/cmd/golangci-lint@latest && \
    # WHITE-BOX: Secret Detection Tools
    go install -v github.com/gitleaks/gitleaks/v8@latest && \
    # WHITE-BOX: Dependency Analysis
    go install -v github.com/sonatype-nexus-community/nancy@latest && \
    # WHITE-BOX: Code Pattern Matching
    go install -v github.com/tomnomnom/gf@latest && \
    go install -v github.com/tomnomnom/waybackurls@latest && \
    # WHITE-BOX: GraphQL Analysis
    go install -v github.com/assetnote/kiterunner/cmd/kr@latest || true

RUN nuclei -update-templates

# =============================================================================
# PYTHON-BASED SECURITY TOOLS (Enhanced for White-Box Scanning)
# =============================================================================
RUN pipx install arjun && \
    pipx install dirsearch && \
    pipx inject dirsearch setuptools && \
    pipx install wafw00f && \
    # WHITE-BOX: Python Static Analysis Tools
    pipx install safety && \
    pipx install pip-audit && \
    pipx install detect-secrets && \
    pipx install pylint && \
    pipx install mypy && \
    pipx install pyright || true && \
    pipx install ruff && \
    pipx install vulture && \
    pipx install dodgy && \
    pipx install dlint || true && \
    # WHITE-BOX: Python Taint Analysis
    pipx install pyre-check || true && \
    # WHITE-BOX: Dependency Scanning
    pipx install cyclonedx-bom && \
    pipx install jake || true && \
    # WHITE-BOX: Code Complexity Analysis
    pipx install radon && \
    pipx install xenon && \
    # WHITE-BOX: Django/Flask Security
    pipx install django-security-check || true && \
    # WHITE-BOX: Infrastructure as Code Scanning
    pipx install checkov && \
    # WHITE-BOX: Dockerfile/Container Analysis
    pipx install dockerfile-security || true

ENV NPM_CONFIG_PREFIX=/home/pentester/.npm-global
RUN mkdir -p /home/pentester/.npm-global

# =============================================================================
# NODE.JS-BASED SECURITY TOOLS (Enhanced for White-Box Scanning)
# =============================================================================
RUN npm install -g retire@latest && \
    npm install -g eslint@latest && \
    npm install -g js-beautify@latest && \
    # WHITE-BOX: JavaScript/TypeScript SAST Tools
    npm install -g @typescript-eslint/parser@latest && \
    npm install -g @typescript-eslint/eslint-plugin@latest && \
    npm install -g eslint-plugin-security@latest && \
    npm install -g eslint-plugin-no-unsanitized@latest || true && \
    # WHITE-BOX: Node.js Vulnerability Scanning
    npm install -g npm-audit-html@latest || true && \
    npm install -g better-npm-audit@latest || true && \
    npm install -g snyk@latest || true && \
    npm install -g audit-ci@latest || true && \
    # WHITE-BOX: Dependency Analysis
    npm install -g depcheck@latest && \
    npm install -g npm-check@latest && \
    npm install -g madge@latest && \
    # WHITE-BOX: Code Quality & Complexity
    npm install -g plato@latest || true && \
    npm install -g complexity-report@latest || true && \
    # WHITE-BOX: Secret Detection
    npm install -g secretlint@latest && \
    # WHITE-BOX: React/Vue/Angular Security
    npm install -g eslint-plugin-react-hooks@latest || true && \
    # WHITE-BOX: GraphQL Analysis
    npm install -g graphql-schema-linter@latest || true && \
    # WHITE-BOX: API Documentation Analysis
    npm install -g @stoplight/spectral-cli@latest || true

WORKDIR /home/pentester/tools
RUN git clone https://github.com/aravind0x7/JS-Snooper.git && \
    chmod +x JS-Snooper/js_snooper.sh && \
    git clone https://github.com/xchopath/jsniper.sh.git && \
    chmod +x jsniper.sh/jsniper.sh && \
    git clone https://github.com/ticarpi/jwt_tool.git && \
    chmod +x jwt_tool/jwt_tool.py

USER root

RUN curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin

RUN apt-get update && apt-get install -y zaproxy

RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

RUN apt-get install -y wapiti

USER pentester

# =============================================================================
# PRIMARY WHITE-BOX SAST TOOLS
# =============================================================================
RUN pipx install semgrep && \
    pipx install bandit && \
    # WHITE-BOX: Additional Python security linters
    pipx install prospector || true && \
    pipx install flake8 && \
    pipx install flake8-bandit || true

RUN npm install -g jshint

# =============================================================================
# ADDITIONAL WHITE-BOX TOOLS (as pentester user)
# =============================================================================

# Clone additional white-box analysis tools
WORKDIR /home/pentester/tools

# WHITE-BOX: NodeJsScan - Node.js SAST
RUN git clone --depth 1 https://github.com/ajinabraham/nodejsscan.git && \
    cd nodejsscan && pip install -r requirements.txt || true

# WHITE-BOX: Graudit - Source Code Auditing
RUN git clone --depth 1 https://github.com/wireghoul/graudit.git && \
    chmod +x graudit/graudit

# WHITE-BOX: FindSecBugs patterns (for reference)
RUN git clone --depth 1 https://github.com/find-sec-bugs/find-sec-bugs.git || true

# WHITE-BOX: PHP Security Checker
RUN git clone --depth 1 https://github.com/fabpot/local-php-security-checker.git || true

# WHITE-BOX: Brakeman patterns (Rails security)
RUN gem install brakeman --user-install || true

# WHITE-BOX: PHPCS Security Audit
RUN git clone --depth 1 https://github.com/FloeDesignTechnologies/phpcs-security-audit.git || true

# WHITE-BOX: Dependency Check wrapper scripts
RUN mkdir -p /home/pentester/tools/dependency-check

USER root

# =============================================================================
# ADDITIONAL ROOT-LEVEL WHITE-BOX TOOLS
# =============================================================================

# WHITE-BOX: CodeQL CLI (if available)
RUN curl -L -o /tmp/codeql.tar.gz https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.tar.gz 2>/dev/null && \
    tar -xzf /tmp/codeql.tar.gz -C /opt/ && \
    ln -sf /opt/codeql/codeql /usr/local/bin/codeql && \
    rm /tmp/codeql.tar.gz || echo "CodeQL installation skipped"

# WHITE-BOX: Bearer CLI (SAST for multiple languages)
RUN curl -sfL https://raw.githubusercontent.com/Bearer/bearer/main/contrib/install.sh | sh -s -- -b /usr/local/bin || true

# WHITE-BOX: Horusec (multi-language SAST)
RUN curl -fsSL https://raw.githubusercontent.com/ZupIT/horusec/main/deployments/scripts/install.sh | bash -s latest || true

# WHITE-BOX: Grype (container & SBOM vulnerability scanner)
RUN curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin || true

# WHITE-BOX: Syft (SBOM generator)
RUN curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin || true

# WHITE-BOX: OSV-Scanner (Google's vulnerability scanner)
RUN go install github.com/google/osv-scanner/cmd/osv-scanner@latest && \
    cp /root/go/bin/osv-scanner /usr/local/bin/ || true

# WHITE-BOX: Terrascan (IaC security)
RUN curl -L "$(curl -s https://api.github.com/repos/tenable/terrascan/releases/latest | grep -o -E 'https://.+?_Linux_x86_64.tar.gz')" > /tmp/terrascan.tar.gz && \
    tar -xf /tmp/terrascan.tar.gz -C /usr/local/bin terrascan && \
    rm /tmp/terrascan.tar.gz || true

# WHITE-BOX: KICS (Keeping Infrastructure as Code Secure)
RUN curl -sfL 'https://raw.githubusercontent.com/Checkmarx/kics/master/install.sh' | bash -s -- -b /usr/local/bin || true

# WHITE-BOX: Hadolint (Dockerfile linter)
RUN curl -L -o /usr/local/bin/hadolint https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64 && \
    chmod +x /usr/local/bin/hadolint || true

# WHITE-BOX: Shellcheck (Shell script analysis)
RUN apt-get update && apt-get install -y shellcheck || true

# WHITE-BOX: SARIF tools for report standardization
RUN pip3 install sarif-tools || true

USER root

RUN apt-get autoremove -y && \
    apt-get autoclean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV PATH="/home/pentester/go/bin:/home/pentester/.local/bin:/home/pentester/.npm-global/bin:/app/venv/bin:/home/pentester/tools/graudit:/opt/codeql:$PATH"
ENV VIRTUAL_ENV="/app/venv"
ENV POETRY_HOME="/opt/poetry"
# WHITE-BOX: Environment variables for scanning tools
ENV GRAUDIT_SIGNATURES=/home/pentester/tools/graudit/signatures
ENV SEMGREP_SEND_METRICS=off
ENV SEMGREP_VERSION_CHECK=false

WORKDIR /app

RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        CAIDO_ARCH="x86_64"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        CAIDO_ARCH="aarch64"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    wget -O caido-cli.tar.gz https://caido.download/releases/v0.48.0/caido-cli-v0.48.0-linux-${CAIDO_ARCH}.tar.gz && \
    tar -xzf caido-cli.tar.gz && \
    chmod +x caido-cli && \
    rm caido-cli.tar.gz && \
    mv caido-cli /usr/local/bin/

ENV STRIX_SANDBOX_MODE=true
ENV PYTHONPATH=/app
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

RUN mkdir -p /workspace && chown -R pentester:pentester /workspace /app

COPY pyproject.toml poetry.lock ./

USER pentester
RUN poetry install --no-root --without dev --extras sandbox
RUN poetry run playwright install chromium

RUN /app/venv/bin/pip install -r /home/pentester/tools/jwt_tool/requirements.txt && \
    ln -s /home/pentester/tools/jwt_tool/jwt_tool.py /home/pentester/.local/bin/jwt_tool

RUN echo "# Sandbox Environment" > README.md

COPY strix/__init__.py strix/
COPY strix/runtime/tool_server.py strix/runtime/__init__.py strix/runtime/runtime.py /app/strix/runtime/

COPY strix/tools/__init__.py strix/tools/registry.py strix/tools/executor.py strix/tools/argument_parser.py /app/strix/tools/

COPY strix/tools/browser/ /app/strix/tools/browser/
COPY strix/tools/file_edit/ /app/strix/tools/file_edit/
COPY strix/tools/notes/ /app/strix/tools/notes/
COPY strix/tools/python/ /app/strix/tools/python/
COPY strix/tools/terminal/ /app/strix/tools/terminal/
COPY strix/tools/proxy/ /app/strix/tools/proxy/

RUN echo 'export PATH="/home/pentester/go/bin:/home/pentester/.local/bin:/home/pentester/.npm-global/bin:$PATH"' >> /home/pentester/.bashrc && \
    echo 'export PATH="/home/pentester/go/bin:/home/pentester/.local/bin:/home/pentester/.npm-global/bin:$PATH"' >> /home/pentester/.profile

USER root
COPY containers/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER pentester
WORKDIR /workspace

ENTRYPOINT ["docker-entrypoint.sh"]
