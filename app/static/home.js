//---------------------------------------------------------------------------------------------------------
// Delete Proof Modal
//---------------------------------------------------------------------------------------------------------

const confirm_delete_proof_modal = document.querySelector("#modal-confirm-delete-proof");

async function delete_proof() {
    const nameEl = confirm_delete_proof_modal.querySelector("#proof-name");
    // close modal: indicate which proof should be deleted
    confirm_delete_proof_modal.close(nameEl.dataset.name);
}

confirm_delete_proof_modal.addEventListener("close", async () => {
    if (confirm_delete_proof_modal.returnValue != "cancel") {
        try {
            await fetch(`api/v1/cbmc/proofs/${confirm_delete_proof_modal.returnValue}`, {
                method: "DELETE",
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
    const nameEl = confirm_delete_proof_modal.querySelector("#proof-name");

    const name = event.target.dataset.name;
    nameEl.textContent = name;
    nameEl.dataset.name = name;

    confirm_delete_proof_modal.returnValue = "cancel";
    confirm_delete_proof_modal.showModal();
}

//---------------------------------------------------------------------------------------------------------
// Delete Result Modal
//---------------------------------------------------------------------------------------------------------

const confirm_delete_result_modal = document.querySelector("#modal-confirm-delete-result");

async function delete_result() {
    const nameEl = confirm_delete_result_modal.querySelector("#result-name");
    // close modal: indicate which proof should be deleted
    confirm_delete_result_modal.close(nameEl.dataset.name);
}

confirm_delete_result_modal.addEventListener("close", async () => {
    if (confirm_delete_result_modal.returnValue != "cancel") {
        try {
            await fetch(`api/v1/cbmc/results/${confirm_delete_result_modal.returnValue}`, {
                method: "DELETE",
            });
        } catch (err) {
            console.error(err);
            alert(`Failed to delete result, check console for details.`);
            return;
        }

        location.reload(true);
    }
});

async function show_confirm_delete_result_modal(event) {
    const nameEl = confirm_delete_result_modal.querySelector("#result-name");

    const name = event.target.dataset.name;
    nameEl.textContent = name;
    nameEl.dataset.name = name;

    confirm_delete_result_modal.returnValue = "cancel";
    confirm_delete_result_modal.showModal();
}

//---------------------------------------------------------------------------------------------------------
// Git-Config Modal
//---------------------------------------------------------------------------------------------------------

const update_git_config_modal = document.querySelector("#modal-edit-git-config");
const update_git_config_modal_alert = update_git_config_modal.querySelector(".alert");
const [git_remote_input, git_branch_input, git_user_input, git_pw_input] =
    update_git_config_modal.querySelectorAll("input");

async function update_git_config(event) {
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
}

async function show_update_git_config_modal() {
    let response;
    try {
        response = await fetch("api/v1/git/config").then((res) => res.json());
    } catch (err) {
        console.error(err);
        alert(`Failed to update git config, check console for details.`);
        return;
    }

    git_pw_input.value = response.password ?? "";
    git_user_input.value = response.username ?? "";
    git_branch_input.value = response.branch ?? "";
    git_remote_input.value = response.remote ?? "";

    update_git_config_modal_alert.classList.add("hidden");
    update_git_config_modal.showModal();
}

//---------------------------------------------------------------------------------------------------------
// Git Pull
//---------------------------------------------------------------------------------------------------------

const git_pull_button = document.querySelector("#btn-git-pull");
const git_pull_modal = document.querySelector("#modal-git-pull");
const git_pull_modal_status = git_pull_modal.querySelector(".status");
const git_pull_modal_alert = git_pull_modal.querySelector(".alert");
const git_pull_modal_spinner = git_pull_modal.querySelector(".spinner");

function git_pull_modal_on_close() {
    git_pull_button.removeAttribute("disabled");
    git_pull_modal_alert.classList.add("hidden");
    git_pull_modal_spinner.classList.remove("hidden");
    git_pull_modal_status.textContent = "";
}

git_pull_modal.addEventListener("close", git_pull_modal_on_close);
git_pull_modal.addEventListener("click", (event) => {
    // only enable closing the modal by clicking the background if an error occured
    if (!git_pull_modal_alert.classList.contains("hidden") && event.target == git_pull_modal) {
        git_pull_modal.close();
    }
});

function git_pull_modal_on_error(error) {
    git_pull_modal_alert.textContent = `Error: ${error.detail}`;
    git_pull_modal_status.textContent = "";
    git_pull_modal_alert.classList.remove("hidden");
    git_pull_modal_spinner.classList.add("hidden");
}

async function pull_sources() {
    let response;
    // disable button and reset modal
    git_pull_button.setAttribute("disabled", "");
    git_pull_modal.showModal();

    git_pull_modal_status.textContent = "Pulling sources...";
    try {
        response = await fetch("api/v1/git/pull", {
            method: "POST",
        });
    } catch (err) {
        console.error(err);
        alert(`Failed to pull sources, check console for details.`);
        git_pull_modal.close();
        return;
    }

    if (!response.ok) {
        const error = await response.json();
        git_pull_modal_on_error(error);
        return;
    }

    git_pull_modal_status.textContent = "Rebuilding doxygen docs...";
    try {
        response = await fetch("api/v1/doxygen/build", {
            method: "POST",
        });
    } catch (err) {
        console.error(err);
        alert(`Failed to rebuild doxygen docs, check console for details.`);
        git_pull_modal.close();
        return;
    }

    if (!response.ok) {
        const error = await response.json();
        git_pull_modal_on_error(error);
        return;
    }

    git_pull_modal.close();
}

//---------------------------------------------------------------------------------------------------------
// Add Proof Modal
//---------------------------------------------------------------------------------------------------------

const PAGE_SIZE = 5;

const add_proof_modal = document.querySelector("#modal-add-proof");
const function_list = add_proof_modal.querySelector("ul[class=list]");
const input_search_function = add_proof_modal.querySelector("input[type=search]");
const pagination = add_proof_modal.querySelector(".pagination");
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
                        <button class="btn-add-proof button success" data-name="${func.name}" data-file="${func.file}" onclick="add_proof(event)">
                            Add
                        </button>
                    </div>
                </li>`
        )
        .join("");

    if (functions.total > PAGE_SIZE) {
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

const previous_page_button = pagination.querySelector("button:first-child");
previous_page_button.addEventListener("click", async (event) => {
    event.preventDefault();
    const offset = parseInt(pagination.dataset.offset, 10) || 0;
    pagination.dataset.offset = Math.max(offset - PAGE_SIZE, 0);
    await search_function();
});

const next_page_button = pagination.querySelector("button:last-child");
next_page_button.addEventListener("click", async (event) => {
    event.preventDefault();
    const offset = parseInt(pagination.dataset.offset, 10) || 0;
    pagination.dataset.offset = offset + PAGE_SIZE;
    await search_function();
});

//---------------------------------------------------------------------------------------------------------
// Proof Execution
//---------------------------------------------------------------------------------------------------------

const run_proofs_button = document.querySelector("#btn-run-proofs");
const cancel_proofs_button = document.querySelector("#btn-cancel-proofs");

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

    location.reload(true);
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

    location.reload(true);
}

//---------------------------------------------------------------------------------------------------------
// Console / Status Updates
//---------------------------------------------------------------------------------------------------------

const output_console = document.querySelector(".console");
const task_status_spinner = document.querySelector(".task-status-spinner");
const current_task_status_indicator = document.querySelector("#current-task-status");

const ws = new WebSocket(`ws://${window.location.host}/api/v1/cbmc/task/output`);

ws.onmessage = (event) => {
    output_console.textContent += event.data;
    output_console.scrollTop = output_console.scrollHeight;
};

ws.onclose = () => {
    current_task_status_indicator.textContent = "None";
    task_status_spinner.classList.add("hidden");
    cancel_proofs_button.setAttribute("disabled", "");
    run_proofs_button.removeAttribute("disabled");
};

//---------------------------------------------------------------------------------------------------------
// Utils
//---------------------------------------------------------------------------------------------------------

let timer;
function debounce(func, timeout = 300) {
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => {
            func.apply(this, args);
        }, timeout);
    };
}
