// im pretty sure this is public. i programmed this in 1 session while hungry as fuck its ROUGH man

if (Math.floor(Math.random() * 5) == 0) {
    document.getElementById('ad').style.display = 'block';
}   // show benjaminperla.hair ad

var pageNum = 1;
var searchQuery = '';
var searchTimeout = null;

const pagesLength = 10; // how many buttons
const pagesDiv = document.getElementById('pages');
const statsBody = document.getElementById('stats-body');
const loadingEl = document.getElementById('loading');
const emptyEl = document.getElementById('empty');

document.getElementById('search-players').addEventListener('input', function () {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        searchQuery = this.value.trim();
        pageNum = 1;
        pagesStart = 1;
        displayInfo();
    }, 300);
});

function createButton(text, fn, cssClass) {
    var button = document.createElement('button');
    button.textContent = text;
    button.setAttribute('value', text);
    button.setAttribute('onclick', fn);
    if (cssClass) button.classList.add(cssClass);
    pagesDiv.appendChild(button);
}

var pagesStart = 1;
function updatePages() {
    pagesDiv.innerHTML = '';
    createButton('\u00AB', 'pageBackward();', 'nav-arrow');
    for (i = 0; i < pagesLength && (i + pagesStart - 1)*10 < data['servers'][serversDropdown.value]['rows']; i++) {
        createButton(i + pagesStart, `changePage(${i + pagesStart});`);
    }
    createButton('\u00BB', 'pageForward();', 'nav-arrow');
    var activeBtn = document.querySelector(`#pages button[value='${pageNum}']`);
    if (activeBtn) activeBtn.classList.add('active');
}

function changePage(page) {
    var oldBtn = document.querySelector(`#pages button[value='${pageNum}']`);
    if (oldBtn) oldBtn.classList.remove('active');
    pageNum = page;
    var newBtn = document.querySelector(`#pages button[value='${pageNum}']`);
    if (newBtn) newBtn.classList.add('active');
    displayInfo();
}

function pageForward() {
    if ((pagesStart + pagesLength - 1)*10 > data['servers'][serversDropdown.value]['rows']) { return; }
    pagesStart += pagesLength;
    pageNum = pagesStart;
    updatePages();
    changePage(pagesStart);
}
function pageBackward() {
    if (pagesStart == 1) { return; }
    pagesStart -= pagesLength;
    pageNum = pagesStart;
    updatePages();
    changePage(pagesStart);
}


// getting basic information
fetch("https://relay.awesome.tf/leaderboard-info", {
    method: "GET"
})
.then(response => response.json())
.then(data => {
    var result = [];
    const keys = Object.keys(data.servers);
    for (key in Object.keys(data.servers)) {
        a = data["servers"][keys[key]];
        a.name = keys[key];
        result.push(a); // WORLD IS A FUCK
    }
    result.sort(function (a, b) {
        return a.rows < b.rows;
    });

    for (const i in result) {
        server = result[i];
        var option = document.createElement('option');
        option.setAttribute('value', server.name);
        textNode = document.createTextNode(server.name);
        option.appendChild(textNode);
        serversDropdown.appendChild(option);
    }

    updateDropdowns(data);
})
.catch((error) => {
    console.error('Error:', error);
    loadingEl.style.display = 'none';
    emptyEl.style.display = 'block';
    emptyEl.textContent = 'Failed to load server data';
    return;
});


async function getInfo(req) {
    fetch("https://relay.awesome.tf/leaderboard", {
        method: "POST",
        body: JSON.stringify(req),
        headers: {
            "Content-type": "application/json; charset=UTF-8"
        }
    })
    .then(response => response.json())
    .then(data => {
        updateInfo(data);
    })
    .catch((error) => {
        console.error('Error:', error);
        return;
    });
}
// takes JSON 'server', 'page', 'stat'

async function displayInfo() {
    loadingEl.classList.add('visible');
    const req = {
        "server": document.getElementById('dropdown-servers').value.toLowerCase(),
        "page": pageNum,
        "stat": document.getElementById('dropdown-stats').value.toLowerCase()
    };
    if (searchQuery) req.search = searchQuery;
    const stats = await getInfo(req);
}

const pageLength = 10;
function updateInfo(info) {
    loadingEl.classList.remove('visible');
    statsBody.innerHTML = '';

    if (!info.results || info.results.length === 0) {
        emptyEl.style.display = 'block';
        return;
    }
    emptyEl.style.display = 'none';

    pagesDiv.style.display = info.is_search ? 'none' : '';

    // Update stat column header
    const statHeader = document.getElementById('stat-header');
    if (statsDropdown.value) {
        statHeader.textContent = statsDropdown.value;
    }

    for (const [n, infoRow] of info.results.entries()) {
        const tableRow = document.createElement('tr');
        const rank = info.is_search ? infoRow.rank : (n + 1) + (pageNum - 1) * pageLength;

        const rankCell = document.createElement('td');
        rankCell.textContent = rank;
        if (rank <= 3 && pageNum === 1 && pagesStart === 1) {
            rankCell.classList.add('top-rank');
            rankCell.style.color = 'var(--accent-orange)';
        }

        const nameCell = document.createElement('td');
        nameCell.textContent = infoRow.name;

        const statCell = document.createElement('td');
        statCell.textContent = infoRow.stat;

        tableRow.appendChild(rankCell);
        tableRow.appendChild(nameCell);
        tableRow.appendChild(statCell);
        statsBody.appendChild(tableRow);
    }


// [][][][][][][][][][][][][] <----- blockchain
}

const serversDropdown = document.getElementById('dropdown-servers');
const statsDropdown = document.getElementById('dropdown-stats');
var data;
function updateDropdowns(leaderboardInfo) {
    if (data != undefined) {
        pageNum = 1;
        pagesStart = 1;
        updatePages();
    }

    if (leaderboardInfo != undefined) { data = leaderboardInfo } else { leaderboardInfo = data }

    const selectedServer = serversDropdown.value;
    statsDropdown.innerHTML = '';
    const statList = leaderboardInfo['servers'][selectedServer]['stats'];
    for (const i in statList) {
        stat = titleCase(statList[i]);

        var option = document.createElement('option');
        option.setAttribute('value', stat);
        textNode = document.createTextNode(stat);
        option.appendChild(textNode);
        statsDropdown.appendChild(option);
    }

    displayInfo();
    updatePages();
}
updateDropdowns();


function titleCase(str) {
    const words = str.split(" ");
    for (let i = 0; i < words.length; i++) {
        words[i] = words[i][0].toUpperCase() + words[i].substr(1);
    }
    return words.join(" ");
}
