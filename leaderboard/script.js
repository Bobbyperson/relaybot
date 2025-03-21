// im pretty sure this is public. i programmed this in 1 session while hungry as fuck its ROUGH man


if (Math.floor(Math.random() * 5) == 0) {
    document.getElementById('ad').style.display = 'block';
}   // show benjaminperla.hair ad

const baseUrl_scoreboard = 'https://leaderboard.bluetick.dev:8383/scoreboard/'
var pageNum = 1;


const filledSquare = document.getElementById('filled-square');

const pagesLength = 10; // how many buttons
const pagesDiv = document.getElementById('pages');
function createButton(text, fn) {
    var button = document.createElement('button');
    var textNode = document.createTextNode(text);
    button.appendChild(textNode);
    button.setAttribute('value', text);
    button.setAttribute('onclick', fn);
    document.getElementById('pages').appendChild(button);
}

var pagesStart = 1;
function updatePages() {
    pagesDiv.innerHTML = '';
    createButton('<<', 'pageBackward();');
    for (i = 0; i < pagesLength && (i + pagesStart - 1)*10 < data['servers'][serversDropdown.value]['rows']; i++) {
        createButton(i + pagesStart, `changePage(${i + pagesStart});`);
    }
    createButton('>>', 'pageForward();');
    document.querySelector(`button[value=\'${pageNum}\']`).classList.add('depressed');
}

function changePage(page) {
    if (document.querySelector(`button[value=\'${pageNum}\']`) != null) {
        document.querySelector(`button[value=\'${pageNum}\']`).classList.remove('depressed');
    }
    pageNum = page;
    document.querySelector(`button[value=\'${pageNum}\']`).classList.add('depressed');
    displayInfo();
}

function pageForward() {
    if ((pagesStart + pagesLength - 1)*10 > data['servers'][serversDropdown.value]['rows']) { return; }
    // ^ if further than data available. -1 because the last page will be truncated
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
// var leaderboardInfo;
fetch("https://relay.bluetick.dev/leaderboard-info", {
    method: "GET"
})
.then(response => response.json())
.then(data => {
    // console.log(data);
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
    // console.log(result);

    for (const i in result) {  // update server list
        server = result[i];
        // console.log(server);

        var option = document.createElement('option');
        option.setAttribute('value', server.name);
        textNode = document.createTextNode(server.name);
        option.appendChild(textNode);
        serversDropdown.appendChild(option);

    }
    
    updateDropdowns(data);
    // return result;
})
.catch((error) => {
    console.error('Error:', error);
    return;
});


async function getInfo(req) {

    // req =
    // {
    //     "server": document.getElementById('dropdown-servers').value.toLowerCase(), 
    //     "page": 1, 
    //     "stat": document.getElementById('dropdown-stats').value.toLowerCase()
    // };

    fetch("https://relay.bluetick.dev/leaderboard", {
        method: "POST",
        body: JSON.stringify(req),
        headers: {
            "Content-type": "application/json; charset=UTF-8"
        }
    })
    .then(response => response.json())
    .then(data => {
        // console.log('Success:', data);
        updateInfo(data);
    })
    .catch((error) => {
        console.error('Error:', error);
        return;
    });

}
// takes JSON 'server', 'page', 'stat'

async function displayInfo() {

    // console.log({
    //     "server": document.getElementById('dropdown-servers').value.toLowerCase(), 
    //     "page": pageNum, 
    //     "stat": document.getElementById('dropdown-stats').value.toLowerCase()
    // });

    const stats = await getInfo({
        "server": document.getElementById('dropdown-servers').value.toLowerCase(), 
        "page": pageNum, 
        "stat": document.getElementById('dropdown-stats').value.toLowerCase()
    });
}

const pageLength = 10;
const statsTable = document.getElementById('stats-table');
function updateInfo(info) {

    while (statsTable.childNodes.length > 2) {
        statsTable.removeChild(statsTable.lastChild);
    }

    var n = 0;

    for (const infoRow of info.results) {
        n++;
        const tableRow = document.createElement('tr');
        var textNode;

        const rank = document.createElement('th');
        rank.classList.add('rank');
        textNode = document.createTextNode(n + (pageNum-1)*pageLength);
        rank.appendChild(textNode);

        const name = document.createElement('th');
        name.classList.add('name');
        textNode = document.createTextNode(infoRow.name);
        name.appendChild(textNode);

        const stat = document.createElement('th');
        stat.classList.add('stat');
        textNode = document.createTextNode(infoRow.stat);
        stat.appendChild(textNode);

        tableRow.appendChild(rank);
        tableRow.appendChild(name);
        tableRow.appendChild(stat);

        statsTable.appendChild(tableRow);
    }



// [][][][][][][][][][][][][] <----- blockchain
}

const serversDropdown = document.getElementById('dropdown-servers');
const statsDropdown = document.getElementById('dropdown-stats');
var data;
function updateDropdowns(leaderboardInfo) {
    if (data != undefined) {  // first time loading into page shouldn't do this
        pageNum = 1;
        pagesStart = 1;
        updatePages();
    }

    // console.log(leaderboardInfo);
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

    // console.log(document.getElementById('dropdown-servers').value, document.getElementById('dropdown-stats').value)
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

// function usernameLookup(event) {
//     event.preventDefault();
//     const query = document.getElementById('search').value;
//     console.log('Search query:', query);
// }