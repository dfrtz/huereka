/**
 * @file User application for displaying networking options and establishing WLAN connections.
 *
 * @summary WLAN connection manager.
 *
 * @author David Fritz
 * @copyright 2025 David Fritz
 * @license MIT
 */

/**
 * WLAN Security names by their numerical type.
 *
 * @type {Object<number, string>}
 */
const SECURITY = {0: "open", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK", 4: "WPA/WPA2-PSK"};

const FORM = document.getElementById("form");
const TABLE = document.getElementById("networks");
const REFRESH = document.getElementById("refresh");
const SUBMIT = document.getElementById("submit");
const STATUS = document.getElementById("status");

/**
 * Create a row for the user to select a network in the primary table.
 *
 * @param {Object} config A WLAN configuration.
 * @returns {HTMLTableRowElement} Row summarizing the network connection.
 */
function getRow(config) {
    const network = document.createElement("td");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "ssid";
    input.value = config["ssid"];
    input.required = true;
    network.replaceChildren(input, document.createTextNode(config["ssid"]));
    const strength = document.createElement("td");
    strength.appendChild(document.createTextNode((100 + config["strength"]).toString()));
    const security = document.createElement("td");
    security.appendChild(document.createTextNode(SECURITY[config["security"]] || `Unknown (${config["security"]})`));
    const row = document.createElement("tr");
    row.replaceChildren(network, strength, security);
    return row;
}

/**
 * Display a message in the status.
 *
 * @param {string} message The text to display.
 */
function showStatusMessage(message) {
    STATUS.replaceChildren(document.createTextNode(message));
}

/**
 * Display a message in the networking table instead of connections.
 *
 * @param {string} message The text to display.
 */
function showTableMessage(message) {
    const td = document.createElement("td");
    td.appendChild(document.createTextNode(message));
    const row = document.createElement("tr");
    row.replaceChildren(document.createElement("td"), td, document.createElement("td"));
    TABLE.replaceChildren(row);
}

/**
 * Load the available connections into the networking table.
 */
function load() {
    REFRESH.disabled = true;
    SUBMIT.disabled = true;
    showTableMessage("Loading...");
    fetch(`${window.location.origin}/networks`).then(response => {
        if (!response.ok) {
            throw new Error("Unexpected response while requesting networks.");
        }
        return response.json();
    }).then(data => {
        if (!data || !data.length) {
            showTableMessage("No networks found.");
        } else {
            const rows = [];
            for (const network of data) {
                if (!network["ssid"]) {
                    continue;
                }
                rows.push(getRow(network));
            }
            TABLE.replaceChildren(...rows);
        }
        REFRESH.disabled = false;
        SUBMIT.disabled = false;
    }).catch(error => {
        showTableMessage("Failed to load. Press 'Refresh' to try again.");
        console.error(error);
        showStatusMessage(error.toString());
        REFRESH.disabled = false;
        SUBMIT.disabled = false;
    });
}

FORM.addEventListener("submit", event => {
    event.preventDefault();
    REFRESH.disabled = true;
    SUBMIT.disabled = true;
    showStatusMessage("Connecting...");
    fetch(event.target.action, {
        method: "POST",
        body: new URLSearchParams(new FormData(event.target)),
    }).then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    }).then(data => {
        const error = data["error"];
        if (error) {
            showStatusMessage(`Failed to connect: ${error}`);
            REFRESH.disabled = false;
            SUBMIT.disabled = false;
        } else {
            showStatusMessage(
                `Successfully connected to ${data["ssid"]} as ${data["hostname"]} on ${data["ifconfig"][0]}. ` +
                "No further configuration allowed through this portal. You may close this page. " +
                "To reconfigure, connect to the device on the new network."
            );
        }
    }).catch(error => {
        showStatusMessage("Failed to connect: " + error.toString());
        REFRESH.disabled = false;
        SUBMIT.disabled = false;
    });
});

load();
