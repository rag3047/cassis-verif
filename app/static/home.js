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
        .map((func) => function_list_item_template.replace(/{{ func\.(\w+) }}/g, (match, p1) => func[p1] || ""))
        .join("");

    // TODO: add event listeners to buttons
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

async function run_all_proofs() {
    let response;

    try {
        response = await fetch(`api/v1/cbmc/task`, {
            method: "POST",
        });
    } catch (err) {
        console.error(err);
        alert(`Failed to run proofs, check console for details.`);
        return;
    }

    if (!response.ok) {
        const error = await response.json();
        // TODO: Make pretty
        alert(`Failed to run proofs: ${error.detail}`);
        return;
    }

    // TODO: establish websocket connection, update console
}

const run_proofs_button = document.querySelector("#btn-run-proofs");
run_proofs_button.addEventListener("click", run_all_proofs);

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

const function_list_item_template = `
<li class="list-item">
    <div>
        <h2>{{ func.name }}</h2>
        <span>{{ func.file }}</span>
    </div>
    <div>
        <button class="btn-add-proof button success" data-name="{{ func.name }}" data-file="{{ func.file }}">
            Add
        </button>
    </div>
</li>`;
