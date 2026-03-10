if (Math.floor(Math.random() * 5) === 0) {
    document.getElementById('ad').style.display = 'block';
}

let allServers = [];
let filteredServers = [];
let serverSearchQuery = '';
let pageNum = 1;
let pagesStart = 1;
let currentPeriod = '30d';
const pagesLength = 10;
const pageLength = 10;

const pagesDiv = document.getElementById('pages');
const scoreboardBody = document.getElementById('scoreboard-body');
const loadingEl = document.getElementById('loading');
const emptyEl = document.getElementById('empty');

document.getElementById('search-servers').addEventListener('input', function () {
    serverSearchQuery = this.value.trim().toLowerCase();
    filteredServers = applySearch(allServers);
    pageNum = 1;
    pagesStart = 1;
    updatePages();
    updateInfo();
});

function applySearch(servers) {
    if (!serverSearchQuery) return servers;
    return servers.filter(s => s.name.toLowerCase().includes(serverSearchQuery));
}

function createButton(text, fn, cssClass) {
    const button = document.createElement('button');
    button.textContent = text;
    button.setAttribute('value', text);
    button.setAttribute('onclick', fn);
    if (cssClass) button.classList.add(cssClass);
    pagesDiv.appendChild(button);
}

function updatePages() {
    if (!filteredServers.length) return;

    pagesDiv.innerHTML = '';

    createButton('\u00AB', 'pageBackward();', 'nav-arrow');

    const totalServers = filteredServers.length;
    for (let i = 0; i < pagesLength && ((i + pagesStart - 1) * pageLength) < totalServers; i++) {
        createButton(i + pagesStart, `changePage(${i + pagesStart});`);
    }

    createButton('\u00BB', 'pageForward();', 'nav-arrow');

    const currentButton = document.querySelector(`#pages button[value='${pageNum}']`);
    if (currentButton) {
        currentButton.classList.add('active');
    }
}

function changePage(page) {
    const oldPageButton = document.querySelector(`#pages button[value='${pageNum}']`);
    if (oldPageButton) {
        oldPageButton.classList.remove('active');
    }

    pageNum = page;

    const newPageButton = document.querySelector(`#pages button[value='${pageNum}']`);
    if (newPageButton) {
        newPageButton.classList.add('active');
    }

    updateInfo();
}

function pageForward() {
    if (!filteredServers.length) return;

    const totalServers = filteredServers.length;
    if ((pagesStart + pagesLength - 1) * pageLength >= totalServers) {
        return;
    }

    pagesStart += pagesLength;
    pageNum = pagesStart;

    updatePages();
    changePage(pageNum);
}

function pageBackward() {
    if (pagesStart === 1) {
        return;
    }

    pagesStart -= pagesLength;
    pageNum = pagesStart;

    updatePages();
    changePage(pageNum);
}

function setFilter(period) {
    currentPeriod = period;

    const labelMap = { '24h': '24H', '7d': '7D', '30d': '30D', '1y': '1Y', 'all': 'All Time' };
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent === labelMap[period]);
    });

    pageNum = 1;
    pagesStart = 1;
    allServers = [];
    scoreboardBody.innerHTML = '';
    emptyEl.style.display = 'none';
    loadingEl.classList.add('visible');
    loadAllServers();
}

async function loadAllServers() {
    // are you a dev? feel free to use this endpoint, let me know what cool stuff you make :D
    fetch(`https://relay.awesome.tf/server-scoreboard?period=${currentPeriod}`, {
        method: "GET"
    })
        .then(response => response.json())
        .then(info => {
            allServers = (info.servers || []).map((s, i) => ({ ...s, rank: i + 1 }));
            filteredServers = applySearch(allServers);
            loadingEl.classList.remove('visible');

            if (filteredServers.length === 0) {
                emptyEl.style.display = 'block';
                return;
            }

            updatePages();
            updateInfo();
        })
        .catch((error) => {
            console.error('Error:', error);
            loadingEl.classList.remove('visible');
            emptyEl.style.display = 'block';
            emptyEl.textContent = 'Failed to load server data';
        });
}

function updateInfo() {
    scoreboardBody.innerHTML = '';

    if (!filteredServers.length) return;

    const startIndex = (pageNum - 1) * pageLength;
    const endIndex = startIndex + pageLength;
    const currentServers = filteredServers.slice(startIndex, endIndex);

    for (let i = 0; i < currentServers.length; i++) {
        const server = currentServers[i];
        const row = document.createElement('tr');
        const displayRank = server.rank;
        const rankCell = document.createElement('td');
        rankCell.textContent = displayRank;
        if (displayRank <= 3) {
            rankCell.style.color = 'var(--accent-orange)';
        }

        const nameCell = document.createElement('td');
        nameCell.textContent = server.name;

        const hours = (server.score * 5 / 60).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        const scoreCell = document.createElement('td');
        scoreCell.textContent = hours;

        row.appendChild(rankCell);
        row.appendChild(nameCell);
        row.appendChild(scoreCell);
        scoreboardBody.appendChild(row);
    }
}

loadAllServers();
