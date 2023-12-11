//---------------------------------------------------------------------------------------------------------
// Globals
//---------------------------------------------------------------------------------------------------------

let has_unsaved_changes = false;

window.addEventListener("beforeunload", (event) => {
    if (has_unsaved_changes) {
        event.preventDefault();
        event.returnValue = true;
    }
});

//---------------------------------------------------------------------------------------------------------
// Monaco Editor
//---------------------------------------------------------------------------------------------------------

let editor;

require.config({ paths: { vs: "static/monaco-editor/min/vs" } });
require(["vs/editor/editor.main"], async function () {
    editor = monaco.editor.create(document.getElementById("editor"), {
        theme: "vs-dark",
        value: "",
        language: "plaintext",
        automaticLayout: true,
    });

    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KEY_S, function (event) {
        // TODO: fix this
        console.log(event);
        console.log("save");
    });

    editor.onDidChangeModelContent(function (event) {
        has_unsaved_changes ||= true;
    });
});

async function on_file_selected(path) {
    const url = "api/v1/files/" + path;

    const code = await fetch(url).then((response) => response.text());
    let model = monaco.editor.getModel(url);

    if (!model) {
        const ext = "." + path.split(".").pop();
        const language =
            monaco.languages.getLanguages().find((lang) => lang.extensions?.includes(ext))?.id ?? "plaintext";
        model = monaco.editor.createModel(code, language, url);
    }

    editor.setModel(model);
}

async function save_file() {
    const model = editor.getModel();

    if (model.uri.toString().startsWith("inmemory://")) {
        return;
    }

    const response = await fetch(model.uri, {
        method: "PUT",
        body: model.getValue(),
    });

    const notification = document.querySelector(".notification");

    if (response.ok) {
        notification.textContent = "Saved";
        notification.classList.add("show-success");
        setTimeout(() => {
            notification.classList.remove("show-success");
        }, 3000);
        has_unsaved_changes = false;
    } else {
        notification.textContent = "Error";
        notification.classList.add("show-error");
        setTimeout(() => {
            notification.classList.remove("show-error");
        }, 3000);
    }
}

const toggle_editor_button = document.querySelector("#btn-toggle-editor");
const editor_container = document.querySelector(".editor-container");

async function toggle_editor() {
    if (editor_container.classList.contains("hidden")) {
        editor_container.classList.remove("hidden");
        toggle_editor_button.textContent = "Hide Editor";
    } else {
        editor_container.classList.add("hidden");
        toggle_editor_button.textContent = "Show Editor";
    }
}

//---------------------------------------------------------------------------------------------------------
// Directory Tree
//---------------------------------------------------------------------------------------------------------

const contextmenus = document.querySelectorAll(".contextmenu");

function show_contextmenu(menu) {
    // create close callback for given context menu
    function close_contextmenu(event) {
        if (event instanceof KeyboardEvent && event.key == "Escape") {
            menu.close();
        }

        if (event instanceof PointerEvent && !menu.contains(event.target)) {
            menu.close();
        }
    }

    // remove close callbacks from document when context menu is closed
    menu.addEventListener("close", () => {
        document.removeEventListener("keydown", close_contextmenu);
        document.removeEventListener("click", close_contextmenu);
    });

    // return callback to show context menu
    return async function (event, node) {
        // close all other context menus
        contextmenus.forEach((ctx_menu) => {
            if (ctx_menu != menu) {
                ctx_menu.close();
            }
        });

        // set data-path attribute on menu items
        menu.querySelectorAll("button").forEach((btn) => {
            btn.dataset.path = node.getUserObject().path;
        });

        menu.style.left = event.clientX + "px";
        menu.style.top = event.clientY + "px";

        // register close callbacks on document
        document.addEventListener("keydown", close_contextmenu);
        document.addEventListener("click", close_contextmenu);

        menu.show();
    };
}

// Note: we use the hidden select (replaced by nice-select2) to retrieve the harness file name
const harness_file = document.querySelector("#sel-proof option[selected]")?.getAttribute("data-harness");
let selected_path = null;
let tree_view = null;

async function build_directory_tree() {
    const root = new TreeNode("root");
    const entries = await fetch("api/v1/files").then((res) => res.json());

    for (const entry of entries) {
        const parts = entry.path.split("/");
        const name = parts.pop();
        entry.toString = () => name;

        let parent = root;
        for (const part of parts) {
            const child = parent.getChildren().find((child) => child.toString() == part);

            if (child) {
                parent = child;
            } else {
                throw new Error("Invalid directory tree");
            }
        }

        const node = new TreeNode(entry, {
            allowChildren: entry.type == "dir",
            forceParent: entry.type == "dir",
            selected: name == harness_file,
            expanded: false,
        });

        parent.addChild(node);
        tree_node_add_events(node, entry);

        if (entry.type == "file" && name == harness_file) {
            selected_path = new TreePath(root, node);
            // TODO: ensure monaco editor is loaded (not always the case, seems to be an issue only when hard-relading the page)
            await on_file_selected(entry.path);
        }
    }

    return new TreeView(root, "#dir-tree", { show_root: false });
}

const contextmenu_file = document.querySelector("#contextmenu-file");
const contextmenu_dir = document.querySelector("#contextmenu-dir");

function tree_node_add_events(node, entry) {
    if (entry.type == "file") {
        node.on("select", async () => {
            await on_file_selected(entry.path);
        });

        node.on("contextmenu", show_contextmenu(contextmenu_file));
    }

    if (entry.type == "dir") {
        node.on("contextmenu", show_contextmenu(contextmenu_dir));
    }
}

function remove_tree_node_by_path(path) {
    let parent = tree_view.getRoot();
    let node = null;

    for (const part of path.split("/")) {
        node = parent.getChildren().find((child) => child.toString() == part);

        if (node.getUserObject().path == path) break;
        parent = node;
    }

    if (node) {
        parent.removeChild(node);
        tree_view.reload();
    }
}

function sort_tree_nodes(node1, node2) {
    const data1 = node1.getUserObject();
    const data2 = node2.getUserObject();

    if (data1.type == data2.type) {
        return node1.toString().localeCompare(node2.toString());
    } else if (data1.type == "dir") {
        return -1;
    } else {
        return 1;
    }
}

/**
 *
 * @param {string} path
 * @param {string} type
 */
async function add_tree_path(path, type) {
    const parts = path.split("/");

    let parent = tree_view.getRoot();
    let temp_node = null;

    let i = 0;
    // skip existing parent nodes
    for (; i < parts.length - 1; i++) {
        const part = parts[i];
        temp_node = parent.getChildren().find((child) => child.toString() == part);

        if (!temp_node) break;
        parent = temp_node;
    }

    // create missing parent nodes (if any)
    for (; i < parts.length - 1; i++) {
        const part = parts[i];
        const entry = {
            path: parts.slice(0, i + 1).join("/"),
            type: "dir",
            toString: () => part,
        };

        const node = new TreeNode(entry, {
            allowChildren: true,
            forceParent: true,
            selected: false,
            expanded: true,
        });

        tree_node_add_events(node, entry);

        parent.addChild(node);
        parent.setExpanded(true);
        parent.getChildren().sort(sort_tree_nodes);
        parent = node;
    }

    // create final node (file or folder)
    const name = parts.pop();
    const entry = {
        path,
        type,
        toString: () => name,
    };

    const node = new TreeNode(entry, {
        allowChildren: type == "dir",
        forceParent: type == "dir",
        selected: false,
        expanded: false,
    });

    tree_node_add_events(node, entry);

    parent.addChild(node);
    parent.setExpanded(true);
    parent.getChildren().sort(sort_tree_nodes);
    tree_view.reload();
}

document.addEventListener("DOMContentLoaded", async () => {
    tree_view = await build_directory_tree();

    if (selected_path) {
        tree_view.expandPath(selected_path);
        tree_view.reload();
    }
});

// TODO: create top level file/folder

//---------------------------------------------------------------------------------------------------------
// Hints
//---------------------------------------------------------------------------------------------------------

const hints_container = document.querySelector(".hints-container");
const hints = hints_container.querySelector(".hints");
const loading_indicator = hints_container.querySelector(".loading");
const no_proof_selected = hints_container.querySelector(".no-proof-selected");
const refresh_hints_button = hints_container.querySelector("#btn-refresh-hints");
const sel_proof = hints_container.querySelector("#sel-proof");

async function refresh_hints(hard_refresh = false) {
    const proof_name = sel_proof.value;

    hints.classList.add("hidden");
    loading_indicator.classList.remove("hidden");
    no_proof_selected.classList.add("hidden");
    refresh_hints_button.removeAttribute("disabled");

    let responses;
    try {
        responses = await Promise.all([
            // TODO get all hints
            fetch(`api/v1/cbmc/proofs/${proof_name}/loops?rebuild=${hard_refresh}`),
        ]);
    } catch (err) {
        console.error(err);
        alert(`Failed to load hints, check console for details.`);
        return;
    }

    if (!responses.every((response) => response.ok)) {
        const error = await responses.find((response) => !response.ok).json();
        alert(`Failed to load hints: ${error.detail}`);
        return;
    }

    // TODO: setup hints
    hints.classList.remove("hidden");
    loading_indicator.classList.add("hidden");
}

document.addEventListener("DOMContentLoaded", function () {
    NiceSelect.bind(document.querySelector("select"), {
        searchable: true,
        searchtext: "Search",
    });
});

//---------------------------------------------------------------------------------------------------------
// Delete File/Folder Modal
//---------------------------------------------------------------------------------------------------------

const confirm_delete_entry_modal = document.querySelector("#modal-confirm-delete-entry");

async function delete_entry() {
    const pathEl = confirm_delete_entry_modal.querySelector("#entry-path");
    // close modal: indicate which proof should be deleted
    confirm_delete_entry_modal.close(pathEl.dataset.path);
}

confirm_delete_entry_modal.addEventListener("close", async () => {
    if (confirm_delete_entry_modal.returnValue != "cancel") {
        let response;

        try {
            response = await fetch(`api/v1/files/${confirm_delete_entry_modal.returnValue}`, {
                method: "DELETE",
            });
        } catch (err) {
            console.error(err);
            alert(`Failed to delete file/folder, check console for details.`);
            return;
        }

        if (!response.ok) {
            const error = await response.json();
            alert(`Failed to delete file/folder: ${error.detail}`);
            return;
        }

        remove_tree_node_by_path(confirm_delete_entry_modal.returnValue);
    }
});

async function show_confirm_delete_entry_modal(event) {
    const pathEl = confirm_delete_entry_modal.querySelector("#entry-path");

    const path = event.target.dataset.path;
    pathEl.textContent = path;
    pathEl.dataset.path = path;

    confirm_delete_entry_modal.returnValue = "cancel";
    confirm_delete_entry_modal.showModal();
}

//---------------------------------------------------------------------------------------------------------
// Create File/Folder Modal
//---------------------------------------------------------------------------------------------------------

const create_entry_modal = document.querySelector("#modal-create-entry");
const create_entry_modal_alert = create_entry_modal.querySelector(".alert");
const create_entry_name_input = create_entry_modal.querySelector("#entry-name");
const create_entry_type_span = create_entry_modal.querySelector("#entry-type");
const create_entry_confirm_button = create_entry_modal.querySelector("#modal-create-entry .button.success");

async function create_entry(event) {
    event.preventDefault();

    if (!create_entry_name_input.value) {
        create_entry_modal_alert.textContent = "Error: Name must not be empty";
        create_entry_modal_alert.classList.remove("hidden");
        return;
    }

    // build path from root to new element
    const path = create_entry_confirm_button.dataset.parent + "/" + create_entry_name_input.value;

    let response;

    try {
        response = await fetch("api/v1/files", {
            method: "POST",
            body: JSON.stringify({
                type: create_entry_type_span.dataset.type,
                path: path,
            }),
            headers: {
                "Content-Type": "application/json",
            },
        });
    } catch (err) {
        console.error(err);
        alert(`Failed to create file/folder, check console for details.`);
        return;
    }

    if (!response.ok) {
        const error = await response.json();
        create_entry_modal_alert.textContent = `Error: ${error.detail}`;
        create_entry_modal_alert.classList.remove("hidden");
        return;
    }

    // update dir_tree
    add_tree_path(path, create_entry_type_span.dataset.type);

    // close modal
    create_entry_modal.close();
}

async function show_create_file_modal(event) {
    create_entry_type_span.textContent = "File";
    create_entry_type_span.dataset.type = "file";

    // reset input
    create_entry_name_input.value = "";
    create_entry_modal_alert.classList.add("hidden");
    create_entry_confirm_button.dataset.parent = event.target.dataset.path;

    create_entry_modal.returnValue = "cancel";
    create_entry_modal.showModal();
}

async function show_create_dir_modal(event) {
    create_entry_type_span.textContent = "Folder";
    create_entry_type_span.dataset.type = "dir";

    // reset input
    create_entry_name_input.value = "";
    create_entry_modal_alert.classList.add("hidden");
    create_entry_confirm_button.dataset.parent = event.target.dataset.path;

    create_entry_modal.returnValue = "cancel";
    create_entry_modal.showModal();
}
