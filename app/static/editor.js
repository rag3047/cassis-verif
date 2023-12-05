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

async function on_changed(path) {
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

const show_editor_button = document.querySelector("#btn-show-editor");
const editor_container = document.querySelector(".editor-container");

async function hide_editor() {
    show_editor_button.classList.remove("hidden");
    editor_container.classList.add("hidden");
}

async function show_editor() {
    show_editor_button.classList.add("hidden");
    editor_container.classList.remove("hidden");
}

//---------------------------------------------------------------------------------------------------------
// Directory Tree
//---------------------------------------------------------------------------------------------------------

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
            expanded: false,
        });

        if (entry.type == "file") {
            node.on("select", async (node) => {
                await on_changed(node.getUserObject().path);
            });
        }

        if (entry.type == "dir") {
            node.on("contextmenu", async (event, node) => {
                console.log("contextmenu", event, node);
            });
        }

        parent.addChild(node);
    }

    return new TreeView(root, "#dir-tree", { show_root: false });
}

build_directory_tree();
