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

const contextmenu_file = document.querySelector("#contextmenu-file");
const contextmenu_dir = document.querySelector("#contextmenu-dir");

// Note: we use the hidden select (replaced by nice-select2) to retrieve the harness file name
const harness_file = document.querySelector("#sel-proof option[selected]")?.getAttribute("data-harness");
let selected_path = null;
let dir_tree = null;

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

        if (entry.type == "file") {
            node.on("select", async (node) => {
                await on_file_selected(entry.path);
            });

            node.on("contextmenu", show_contextmenu(contextmenu_file));

            if (name == harness_file) {
                selected_path = new TreePath(root, node);
                // TODO: ensure monaco editor is loaded (not always the case, seems to be an issue only when hard-relading the page)
                await on_file_selected(entry.path);
            }
        }

        if (entry.type == "dir") {
            node.on("contextmenu", show_contextmenu(contextmenu_dir));
        }
    }

    return new TreeView(root, "#dir-tree", { show_root: false });
}

function remove_tree_node_by_path(path) {
    let parent = dir_tree.getRoot();
    let node = null;

    for (const part of path.split("/")) {
        node = parent.getChildren().find((child) => child.toString() == part);

        if (node.getUserObject().path == path) break;
        parent = node;
    }

    if (node) {
        parent.removeChild(node);
        dir_tree.reload();
    }
}

function add_tree_node(path, type) {
    // TODO
}

document.addEventListener("DOMContentLoaded", async () => {
    dir_tree = await build_directory_tree();

    if (selected_path) {
        dir_tree.expandPath(selected_path);
        dir_tree.reload();
    }
});

//---------------------------------------------------------------------------------------------------------
// Hints
//---------------------------------------------------------------------------------------------------------

async function on_proof_select(event) {
    console.log(event);
}

// NiceSelect.bind(document.querySelector("#sel-proof"), {
//     searchable: true,
//     placeholder: "select",
//     searchtext: "zoek",
//     selectedtext: "geselecteerd",
// });

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
    if (!create_entry_name_input.value) {
        event.preventDefault();
        create_entry_modal_alert.textContent = "Error: Name must not be empty";
        create_entry_modal_alert.classList.remove("hidden");
        return;
    }

    // build path from root to new element
    const path = create_entry_confirm_button.dataset.parent + "/" + create_entry_name_input.value;

    // close modal
    confirm_delete_entry_modal.close(path);
}

create_entry_modal.addEventListener("close", async () => {
    if (create_entry_modal.returnValue != "cancel") {
        let response;

        try {
            response = await fetch("api/v1/files", {
                method: "POST",
                body: JSON.stringify({
                    type: create_entry_type_span.dataset.type,
                    path: create_entry_modal.returnValue,
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
            alert(`Failed to create file/folder: ${error.detail}`);
            return;
        }

        // update dir_tree
        add_tree_node(create_entry_modal.returnValue, create_entry_type_span.dataset.type);
    }
});

async function show_create_file_modal(event) {
    create_entry_type_span.textContent = "File";
    create_entry_type_span.dataset.type = "file";

    // reset input
    create_entry_name_input.value = "";
    create_entry_confirm_button.dataset.parent = event.target.dataset.path;

    create_entry_modal.returnValue = "cancel";
    create_entry_modal.showModal();
}

async function show_create_dir_modal(event) {
    create_entry_type_span.textContent = "Folder";
    create_entry_type_span.dataset.type = "dir";

    // reset input
    create_entry_name_input.value = "";
    create_entry_confirm_button.dataset.parent = event.target.dataset.path;

    create_entry_modal.returnValue = "cancel";
    create_entry_modal.showModal();
}
