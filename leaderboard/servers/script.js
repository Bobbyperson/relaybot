if (Math.floor(Math.random() * 5) === 0) {
    document.getElementById('ad').style.display = 'block';
}

let allServers = [];
let pageNum = 1;
let pagesStart = 1;
const pagesLength = 10;
const pageLength = 10;

const pagesDiv = document.getElementById('pages');
const scoreboardTable = document.getElementById('scoreboard-table');

function createButton(text, fn) {
    const button = document.createElement('button');
    const textNode = document.createTextNode(text);

    button.appendChild(textNode);
    button.setAttribute('value', text);
    button.setAttribute('onclick', fn);

    pagesDiv.appendChild(button);
}

function updatePages() {
    if (!allServers.length) return;

    pagesDiv.innerHTML = '';

    createButton('<<', 'pageBackward();');

    const totalServers = allServers.length;
    for (let i = 0; i < pagesLength && ((i + pagesStart - 1) * pageLength) < totalServers; i++) {
        createButton(i + pagesStart, `changePage(${i + pagesStart});`);
    }

    createButton('>>', 'pageForward();');

    const currentButton = document.querySelector(`button[value='${pageNum}']`);
    if (currentButton) {
        currentButton.classList.add('depressed');
    }
}


function changePage(page) {
    const oldPageButton = document.querySelector(`button[value='${pageNum}']`);
    if (oldPageButton) {
        oldPageButton.classList.remove('depressed');
    }

    pageNum = page;

    const newPageButton = document.querySelector(`button[value='${pageNum}']`);
    if (newPageButton) {
        newPageButton.classList.add('depressed');
    }

    updateInfo();
}

function pageForward() {
    if (!allServers.length) return;

    const totalServers = allServers.length;
    // Avoid going beyond the number of servers
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

async function loadAllServers() {
    // are you a dev? feel free to use this endpoint, let me know what cool stuff you make :D
    fetch("https://relay.awesome.tf/server-scoreboard", {
        method: "GET"
    })
        .then(response => response.json())
        .then(info => {
            // `info` should be { servers: [{name, score}, ...] }
            allServers = info.servers || [];

            updatePages();
            updateInfo();
        })
        .catch((error) => {
            console.error('Error:', error);
        });
}

function updateInfo() {
    while (scoreboardTable.rows.length > 1) {
        scoreboardTable.deleteRow(scoreboardTable.rows.length - 1);
    }

    if (!allServers.length) return;

    const startIndex = (pageNum - 1) * pageLength;
    const endIndex = startIndex + pageLength;
    const currentServers = allServers.slice(startIndex, endIndex);

    for (let i = 0; i < currentServers.length; i++) {
        const server = currentServers[i];
        const row = scoreboardTable.insertRow();

        // Rank cell
        const rankCell = row.insertCell();
        rankCell.classList.add('rank');
        rankCell.textContent = startIndex + i + 1;

        // Server Name cell
        const nameCell = row.insertCell();
        nameCell.classList.add('name');
        nameCell.textContent = server.name;

        // Score cell
        const scoreCell = row.insertCell();
        scoreCell.classList.add('score');
        scoreCell.textContent = server.score;
    }
}

loadAllServers();
