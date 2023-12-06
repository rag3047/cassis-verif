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

async function build_directory_tree() {
    const root = new TreeNode("root");
    const entries = await fetch("api/v1/files").then((res) => res.json());

    for (const entry of entries) {
        const parts = entry.path.split("/");
        const name = parts.pop();
        entry.toString = () => name;

        let parent = root;
        for (const part of parts) {
            const child = parent.getChildren().find((child) => child.getUserObject().toString() == part);

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
                // TODO: ensure monaco editor is loaded (not always the case)
                await on_file_selected(entry.path);
            }
        }

        if (entry.type == "dir") {
            node.on("contextmenu", show_contextmenu(contextmenu_dir));
        }
    }

    return new TreeView(root, "#dir-tree", { show_root: false });
}

build_directory_tree().then((tree) => {
    if (selected_path) {
        tree.expandPath(selected_path);
        tree.reload();
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
    const nameEl = confirm_delete_entry_modal.querySelector("#entry-name");
    // close modal: indicate which proof should be deleted
    confirm_delete_entry_modal.close(nameEl.dataset.path);
}

confirm_delete_entry_modal.addEventListener("close", async () => {
    if (confirm_delete_entry_modal.returnValue != "cancel") {
        try {
            // TODO
            // await fetch(`api/v1/cbmc/proofs/${confirm_delete_entry_modal.returnValue}`, {
            //     method: "DELETE",
            // });
        } catch (err) {
            console.error(err);
            alert(`Failed to delete proof, check console for details.`);
            return;
        }

        // TODO check: is this viable? might lose edits in editor? -> only update/reload dir tree?
        location.reload(true);
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
