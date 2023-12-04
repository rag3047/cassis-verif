//---------------------------------------------------------------------------------------------------------
// Delete Modal
//---------------------------------------------------------------------------------------------------------

const confirm_delete_modal = document.querySelector("#modal-confirm-delete");
const confirm_delete_button = confirm_delete_modal.querySelector(".modal-buttons button:first-child");

confirm_delete_button.addEventListener("click", async () => {
    // close modal: indicate which proof should be deleted
    confirm_delete_modal.close(confirm_delete_button.dataset.name);
});

confirm_delete_modal.addEventListener("close", async () => {
    if (confirm_delete_modal.returnValue != "cancel") {
        try {
            await fetch(`api/v1/cbmc/proofs/${confirm_delete_modal.returnValue}`, {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                },
            });
        } catch (err) {
            console.error(err);
            alert(`Failed to delete proof, check console for details.`);
            return;
        }

        location.reload(true);
    }
});

async function show_confirm_delete_proof_modal(event) {
    const nameEl = confirm_delete_modal.querySelector("#proof-name");

    const name = event.target.dataset.name;
    nameEl.textContent = name;
    confirm_delete_button.dataset.name = name;

    confirm_delete_modal.returnValue = "cancel";
    confirm_delete_modal.showModal();
}

const delete_buttons = document.querySelectorAll(".btn-delete-proof");

for (const btn of delete_buttons) {
    btn.addEventListener("click", show_confirm_delete_proof_modal);
}

//---------------------------------------------------------------------------------------------------------
// Git-Config Modal
//---------------------------------------------------------------------------------------------------------

const update_git_config_modal = document.querySelector("#modal-edit-git-config");
const update_git_config_confirm_button = update_git_config_modal.querySelector(".modal-buttons button:first-child");
const update_git_config_modal_alert = update_git_config_modal.querySelector(".alert");
const [git_remote_input, git_branch_input, git_user_input, git_pw_input] =
    update_git_config_modal.querySelectorAll("input");

update_git_config_confirm_button.addEventListener("click", async (event) => {
    event.preventDefault();

    const git_pw_value = git_pw_input.value;
    const is_pw_changed = git_pw_value != "" && git_pw_value.match(/\*+/) == null;

    let response;
    try {
        response = await fetch("api/v1/git/config", {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                remote: git_remote_input.value,
                branch: git_branch_input.value,
                username: git_user_input.value || null,
                password: is_pw_changed ? git_pw_value : null,
            }),
        }).then((res) => res.json());
    } catch (err) {
        console.error(err);
        alert(`Failed to update git config, check console for details.`);
        return;
    }

    if (response.error_code) {
        update_git_config_modal_alert.textContent = `Error: ${response.detail}`;
        update_git_config_modal_alert.classList.remove("hidden");
        return;
    }

    git_pw_input.value = response.password;
    git_user_input.value = response.username;
    git_branch_input.value = response.branch;
    git_remote_input.value = response.remote;

    update_git_config_modal.close();
});

async function show_update_git_config_modal() {
    let response;
    try {
        response = await fetch("api/v1/git/config").then((res) => res.json());
    } catch (err) {
        console.error(err);
        alert(`Failed to update git config, check console for details.`);
        return;
    }

    if (response.error_code) {
        update_git_config_modal_alert.textContent = `Error: ${response.detail}`;
        update_git_config_modal_alert.classList.remove("hidden");
        return;
    }

    git_pw_input.value = response.password;
    git_user_input.value = response.username;
    git_branch_input.value = response.branch;
    git_remote_input.value = response.remote;

    update_git_config_modal_alert.classList.add("hidden");
    update_git_config_modal.showModal();
}

const update_git_config_button = document.querySelector("#btn-show-edit-git-config-modal");
update_git_config_button.addEventListener("click", show_update_git_config_modal);

//---------------------------------------------------------------------------------------------------------
// Add Proof Modal
//---------------------------------------------------------------------------------------------------------

const PAGE_SIZE = 5;
const add_proof_modal = document.querySelector("#modal-add-proof");
const function_list = add_proof_modal.querySelector("ul[class=list]");
const input_search_function = add_proof_modal.querySelector("input[type=search]");
const pagination = add_proof_modal.querySelector(".pagination");
const previous_page_button = pagination.querySelector("button:first-child");
const next_page_button = pagination.querySelector("button:last-child");
const add_proof_modal_alert = add_proof_modal.querySelector(".alert");

add_proof_modal.addEventListener("close", async () => {
    if (add_proof_modal.returnValue == "confirm") {
        // reload page if a proof was added
        location.reload(true);
    }
});

async function show_add_proof_modal() {
    // reset modal
    pagination.dataset.offset = 0;
    input_search_function.value = "";
    function_list.innerHTML = '<li class="list-item-empty"><h2>Please enter a function name...</h2></li>';
    add_proof_modal_alert.classList.add("hidden");
    pagination.classList.add("hidden");

    add_proof_modal.returnValue = "cancel";
    add_proof_modal.showModal();
}

const add_proof_button = document.querySelector("#btn-show-add-proof-modal");
add_proof_button.addEventListener("click", show_add_proof_modal);

async function add_proof(event) {
    event.preventDefault();
    const func_name = event.target.dataset.name;
    const func_file = event.target.dataset.file;

    let response;
    try {
        response = await fetch(`api/v1/cbmc/proofs`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                name: func_name,
                src: func_file,
            }),
        }).then((res) => res.json());
    } catch (err) {
        console.error(err);
        alert(`Failed to add proof, check console for details.`);
        return;
    }

    if (response.error_code) {
        add_proof_modal_alert.textContent = `Error: ${response.detail}`;
        add_proof_modal_alert.classList.remove("hidden");
        return;
    }

    // indicate that a proof was added -> reload page
    add_proof_modal.close("confirm");
}

async function search_function() {
    const filter = input_search_function.value;
    const offset = parseInt(pagination.dataset.offset, 10) || 0;

    if (filter == "") {
        function_list.innerHTML = '<li class="list-item-empty"><h2>Please enter a function name...</h2></li>';
        pagination.classList.add("hidden");
        return;
    }

    // TODO: Fix modal resizing issue...
    // display loading indicator...
    function_list.innerHTML = '<li class="list-item-empty"><div class="lds-dual-ring"></div></li>';

    let functions;
    try {
        functions = await fetch(`api/v1/ctags/functions?filter=${filter}&limit=${PAGE_SIZE}&offset=${offset}`) //
            .then((res) => res.json());
    } catch (err) {
        console.error(err);
        alert(`Failed to load functions, check console for details.`);
        return;
    }

    if (functions.data.length == 0) {
        function_list.innerHTML = '<li class="list-item-empty"><h2>No functions found...</h2></li>';
        return;
    }

    function_list.innerHTML = functions.data
        .map(
            (func) => `
                <li class="list-item">
                    <div>
                        <h2>${func.name}</h2>
                        <span>${func.file}</span>
                    </div>
                    <div>
                        <button class="btn-add-proof button success" data-name="${func.name}" data-file="${func.file}">
                            Add
                        </button>
                    </div>
                </li>`
        )
        .join("");

    // add event listeners to buttons
    const add_buttons = function_list.querySelectorAll(".btn-add-proof");
    for (const btn of add_buttons) {
        btn.addEventListener("click", add_proof);
    }

    if (functions.cursor < functions.total) {
        pagination.classList.remove("hidden");
        // TODO: add page buttons
        // TODO: show total number of results
    } else {
        pagination.classList.add("hidden");
    }
}

input_search_function.addEventListener(
    "input",
    debounce(async () => {
        // reset pagination
        pagination.dataset.offset = 0;
        await search_function();
    }, 300)
);

previous_page_button.addEventListener("click", async (event) => {
    event.preventDefault();
    const offset = parseInt(pagination.dataset.offset, 10) || 0;
    pagination.dataset.offset = Math.max(offset - PAGE_SIZE, 0);
    await search_function();
});

next_page_button.addEventListener("click", async (event) => {
    event.preventDefault();
    const offset = parseInt(pagination.dataset.offset, 10) || 0;
    pagination.dataset.offset = offset + PAGE_SIZE;
    await search_function();
});

//---------------------------------------------------------------------------------------------------------
// Proof Execution
//---------------------------------------------------------------------------------------------------------

const output_console = document.querySelector(".console");
const run_proofs_button = document.querySelector("#btn-run-proofs");
const cancel_proofs_button = document.querySelector("#btn-cancel-proofs"); // TODO
const proof_run_table = document.querySelector(".proof-runs");
const task_status_spinner = document.querySelector(".task-status-spinner");

async function run_all_proofs() {
    run_proofs_button.setAttribute("disabled", "");

    let response;

    try {
        response = await fetch(`api/v1/cbmc/task`, {
            method: "POST",
        }).then((res) => res.json());
    } catch (err) {
        console.error(err);
        alert(`Failed to run proofs, check console for details.`);
        run_proofs_button.removeAttribute("disabled");
        return;
    }

    if (response.error_code) {
        // TODO: Make pretty
        alert(`Failed to run proofs: ${response.detail}`);
        run_proofs_button.removeAttribute("disabled");
        return;
    }

    cancel_proofs_button.removeAttribute("disabled");
    task_status_spinner.classList.remove("hidden");
    output_console.textContent = "";

    // refresh proof run table
    await refresh_proof_runs_table();

    await start_status_updater();
}

run_proofs_button.addEventListener("click", run_all_proofs);

async function refresh_proof_runs_table() {
    let response;
    try {
        response = await fetch(`api/v1/cbmc/task/runs`).then((res) => res.json());
    } catch (err) {
        console.error(err);
        alert(`Failed to load proof runs, check console for details.`);
        return;
    }

    proof_run_table.innerHTML =
        `<li class="table-item">
            <h4 class="width-25">Start-Time</h4>
            <h4 class="width-50">Name</h4>
            <h4 class="width-25">Actions</h4>
        </li>` +
        response
            .map(
                // TODO: Fix this -> buttons layout etc.
                (proof_run) =>
                    `<li class="table-item">
                        <span class="width-25">${moment(proof_run.start_date).format("YYYY-MM-DD HH:mm:ss")}</span>
                        <a class="width-50" href="results?version=${proof_run.name}">${proof_run.name}</a>
                        <span class="width-25">
                            <button class="button download" data-version="${proof_run.name}">Download</button>
                            <button class="button danger delete" data-version="${proof_run.name}">Delete</button>
                        </span>
                    </li>`
            )
            .join("");

    const delete_links = proof_run_table.querySelectorAll(".list-item .delete");
    for (const link of delete_links) {
        // TODO: add confirmation modal
        link.addEventListener("click", delete_proof_run);
    }
}

async function cancel_proof_run() {
    let response;
    try {
        response = await fetch(`api/v1/cbmc/task`, {
            method: "DELETE",
        });
    } catch (err) {
        console.error(err);
        alert(`Failed to cancel proof run, check console for details.`);
        return;
    }

    if (!response.ok) {
        // TODO: make pretty
        const error = await response.json();
        alert(`Failed to cancel proof run: ${error.detail}`);
        return;
    }

    cancel_proofs_button.setAttribute("disabled", "");
    run_proofs_button.removeAttribute("disabled");
    task_status_spinner.classList.add("hidden");

    // TODO: fix
    // // refresh proof run table (cancelled run will be removed)
    // await refresh_proof_runs_table();
}

cancel_proofs_button.addEventListener("click", cancel_proof_run);

async function delete_proof_run(event) {
    event.preventDefault();

    const version = event.target.dataset.version;

    let response;
    try {
        response = await fetch(`api/v1/cbmc/task/results/${version}`, {
            method: "DELETE",
        });
    } catch (err) {
        console.error(err);
        alert(`Failed to delete proof run, check console for details.`);
        return;
    }

    if (!response.ok) {
        // TODO: make pretty
        const error = await response.json();
        alert(`Failed to delete proof run: ${error.detail}`);
        return;
    }

    await refresh_proof_runs_table();
}

const delete_links = proof_run_table.querySelectorAll(".list-item .delete");
for (const link of delete_links) {
    link.addEventListener("click", delete_proof_run);
}

const current_task_status_indicator = document.querySelector("#current-task-status");

// TODO: replace this with websocket connection...
async function start_status_updater() {
    const current_task_status_updater = setInterval(async () => {
        let response;

        try {
            response = await fetch(`api/v1/cbmc/task/status`).then((res) => res.json());
        } catch (err) {
            console.error(err);
            current_task_status_indicator.textContent = "Unknown";
            cancel_proofs_button.setAttribute("disabled", "");
            run_proofs_button.setAttribute("disabled", "");
            return;
        }

        if (response.is_running) {
            current_task_status_indicator.textContent = "Running";
            task_status_spinner.classList.remove("hidden");
            cancel_proofs_button.removeAttribute("disabled");
            run_proofs_button.setAttribute("disabled", "");
        } else {
            current_task_status_indicator.textContent = "None";
            task_status_spinner.classList.add("hidden");
            cancel_proofs_button.setAttribute("disabled", "");
            run_proofs_button.removeAttribute("disabled");
            clearInterval(current_task_status_updater);
        }
    }, 5000);
}

// initially trigger status updater upon page load
start_status_updater();

//---------------------------------------------------------------------------------------------------------
// Console
//---------------------------------------------------------------------------------------------------------

const ws = new WebSocket(`ws://${window.location.host}/api/v1/cbmc/task/output`);
ws.onmessage = (event) => {
    output_console.textContent += event.data;
    output_console.scrollTop = output_console.scrollHeight;
};

//---------------------------------------------------------------------------------------------------------
// Utils
//---------------------------------------------------------------------------------------------------------

function debounce(func, timeout = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => {
            func.apply(this, args);
        }, timeout);
    };
}
