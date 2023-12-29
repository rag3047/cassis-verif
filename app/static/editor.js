//---------------------------------------------------------------------------------------------------------
// Globals
//---------------------------------------------------------------------------------------------------------

// stores the URIs of all unsaved files
let unsaved_changes = new Set();

window.addEventListener("beforeunload", (event) => {
    if (unsaved_changes.size > 0) {
        event.preventDefault();
        event.returnValue = true;
    }
});

//---------------------------------------------------------------------------------------------------------
// Monaco Editor
//---------------------------------------------------------------------------------------------------------

let editor = null;
let selected_file = null;

require.config({ paths: { vs: "static/monaco-editor/min/vs" } });
require(["vs/editor/editor.main"], async function () {
    editor = monaco.editor.create(document.getElementById("editor"), {
        theme: "vs-dark",
        value: "",
        language: "plaintext",
        automaticLayout: true,
    });

    editor.onKeyDown(async (event) => {
        if (event.ctrlKey && event.code == "KeyS") {
            event.preventDefault();
            await save_file();
        }
    });

    editor.onDidChangeModelContent(function (event) {
        unsaved_changes.add(editor.getModel().uri.toString());
        // TODO: mark tab as unsaved
        document.querySelector(".tab.active").classList.add("unsaved");
    });

    if (selected_file) {
        await on_file_selected(selected_file);
    }
});

async function on_file_selected(path) {
    const uri = "api/v1/files/" + encodeURIComponent(path);
    let model = monaco.editor.getModel(uri);

    if (!model) {
        const code = await fetch(uri).then((response) => response.text());
        const ext = "." + path.split(".").pop();
        const language =
            monaco.languages.getLanguages().find((lang) => lang.extensions?.includes(ext))?.id ?? "plaintext";
        model = monaco.editor.createModel(code, language, uri);
        // add new Tab
        add_editor_tab(path, uri);
    } else {
        // select existing tab
        select_editor_tab_by_uri(uri);
    }

    editor.setModel(model);
}

const notification = document.querySelector(".notification");

notification.addEventListener("click", () => {
    notification.classList.remove("show-success");
    notification.classList.remove("show-error");
});

async function save_file() {
    const model = editor.getModel();

    // cannot save inmemory files (e.g. no file selected)
    if (model.uri.toString().startsWith("inmemory://")) return;
    // nothing to save
    if (!unsaved_changes.has(model.uri.toString())) return;

    const response = await fetch(model.uri, {
        method: "PUT",
        body: model.getValue(),
    });

    if (response.ok) {
        notification.textContent = "Saved";
        notification.classList.add("show-success");
        setTimeout(() => {
            notification.classList.remove("show-success");
        }, 3000);
        unsaved_changes.delete(model.uri.toString());
        document.querySelector(".tab.active").classList.remove("unsaved");
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

const tab_list = editor_container.querySelector(".tab-list");

function add_editor_tab(path, uri) {
    const current_tab = tab_list.querySelector(".tab.active");

    if (current_tab) {
        current_tab.classList.remove("active");
    }

    tab_list.innerHTML =
        `<div class="tab active" data-uri="${uri}" data-path="${path}" onclick="on_editor_tab_clicked(event)">
            <span>${path.split("/").pop()}</span>
            <button class="close" onclick="close_editor_tab(event)">X</button>
        </div>\n` + tab_list.innerHTML;
}

function select_editor_tab_by_uri(uri) {
    const current_tab = tab_list.querySelector(".tab.active");

    if (current_tab) {
        current_tab.classList.remove("active");
    }

    const selected_tab = tab_list.querySelector(`.tab[data-uri="${uri}"]`);
    selected_tab.classList.add("active");
}

async function close_editor_tab(event) {
    event.stopPropagation();
    const tab = event.target.parentElement;
    const uri = tab.dataset.uri;

    // auto save file if it has unsaved changes
    if (unsaved_changes.has(uri)) {
        await save_file();
    }

    const model = monaco.editor.getModel(uri);
    model.dispose();

    if (tab.classList.contains("active")) {
        const tab_to_select = tab.previousElementSibling ?? tab.nextElementSibling;

        if (tab_to_select.classList.contains("tab")) {
            tab_to_select.click();
        }
    }

    tab.remove();
}

// TODO: add context menu to save file
async function on_editor_tab_clicked(event) {
    const uri = event.target.dataset.uri;
    const path = event.target.dataset.path;
    const model = monaco.editor.getModel(uri);
    editor.setModel(model);
    select_editor_tab_by_uri(uri);
    select_tree_node_by_path(path);
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
let tree_view = null;

async function build_directory_tree() {
    const root = new TreeNode("root");
    const entries = await fetch("api/v1/files").then((res) => res.json());
    let selected_path = null;

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

            // Load selected file: sometimes the editor is not yet loeaded (e.g. when using a
            // hard reload). In this case we store the selected file path and load it once the
            // editor is ready.
            if (editor != null) {
                await on_file_selected(entry.path);
            } else {
                selected_file = entry.path;
            }
        }
    }

    const view = new TreeView(root, "#dir-tree", { show_root: false });

    if (selected_path) {
        view.expandPath(selected_path);
        view.reload();
    }

    return view;
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

function select_tree_node_by_path(path) {
    let parent = tree_view.getRoot();
    let node = null;

    for (const part of path.split("/")) {
        node = parent.getChildren().find((child) => child.toString() == part);

        if (node.getUserObject().path == path) break;
        parent = node;
    }

    if (node) {
        const tree_path = new TreePath(tree_view.getRoot(), node);
        tree_view.expandPath(tree_path);
        tree_view.getSelectedNodes().forEach((node) => node.setSelected(false));
        node.setSelected(true);
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

// Build directory tree on page load
document.addEventListener("DOMContentLoaded", async () => {
    tree_view = await build_directory_tree();
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
    const file_name = sel_proof.querySelector(`option[value="${proof_name}"]`).dataset.src;

    hints.classList.add("hidden");
    loading_indicator.classList.remove("hidden");
    no_proof_selected.classList.add("hidden");
    refresh_hints_button.removeAttribute("disabled");

    // TODO: if hard_refresh: rebuild doxygen docs

    let responses;
    try {
        const get_params = `file-name=${encodeURIComponent(file_name.split("/").pop())}&func-name=${proof_name}`;

        responses = await Promise.all([
            fetch(`api/v1/cbmc/proofs/${proof_name}/loops?rebuild=${hard_refresh}`),
            fetch(`api/v1/doxygen/callgraphs?${get_params}`),
            fetch(`api/v1/doxygen/function-params?${get_params}`),
            fetch(`api/v1/doxygen/function-refs?${get_params}`),
        ]).then((responses) => Promise.all(responses.map((response) => response.json())));
    } catch (err) {
        console.error(err);
        alert(`Failed to load hints, check console for details.`);
        return;
    }

    const [loops, graphs, params, refs] = responses;

    await refresh_loop_unwinding(loops);
    await refresh_callgraphs(graphs);
    await refresh_function_param_table(params);
    await refresh_ref_table(refs);

    hints.classList.remove("hidden");
    loading_indicator.classList.add("hidden");
}

const context = hints_container.querySelector(".context");
const param_table = context.querySelector(".param-table");
const context_error = hints_container.querySelector(".context-error");

async function refresh_function_param_table(params) {
    if (params.error_code) {
        context.classList.add("hidden");
        context_error.classList.remove("hidden");
        return;
    } else {
        context.classList.remove("hidden");
        context_error.classList.add("hidden");
    }

    let html = `
        <li class="table-item">
            <h4 class="width-50">Name</h4>
            <h4 class="width-50">Type</h4>
        </li>\n`;

    for (const param of params) {
        let type = param.type;

        if (param.ref) {
            type = `<a target="_blank" href="doxygen?href=${encodeURIComponent(param.ref)}.html">${param.type}</a>`;
        }

        html += `
            <li class="table-item">
                <div class="width-50">${param.name}</div>
                <div class="width-50">${type}</div>
            </li>\n`;
    }

    param_table.innerHTML = html;
}

const ref_table = context.querySelector(".ref-table");

async function refresh_ref_table(refs) {
    if (refs.error_code) {
        context.classList.add("hidden");
        context_error.classList.remove("hidden");
        return;
    } else {
        context.classList.remove("hidden");
        context_error.classList.add("hidden");
    }

    let html = `
        <li class="table-item">
            <h4 class="width-50">Name</h4>
            <h4 class="width-50">Type</h4>
        </li>\n`;

    for (const ref of refs) {
        html += `
            <li class="table-item">
                <div class="width-50">${ref.name}</div>
                <div class="width-50">${ref.type}</div>
            </li>\n`;
    }

    ref_table.innerHTML = html;
}

const callgraphs = hints_container.querySelector(".callgraphs");
const callgraph_error = hints_container.querySelector(".callgraph-error");
const cgraph = callgraphs.querySelector(".cgraph");
const cgraph_link = callgraphs.querySelector(".cgraph-link");
const icgraph = callgraphs.querySelector(".icgraph");
const icgraph_link = callgraphs.querySelector(".icgraph-link");
const doxygen_link = hints_container.querySelector("#doxygen-link");

async function refresh_callgraphs(graphs) {
    if (graphs.error_code) {
        callgraphs.classList.add("hidden");
        callgraph_error.classList.remove("hidden");
        return;
    } else {
        callgraphs.classList.remove("hidden");
        callgraph_error.classList.add("hidden");
    }

    doxygen_link.href = "doxygen?href=" + encodeURIComponent(graphs.file_href);

    const prefix = "api/v1/doxygen/docs/";
    cgraph_link.href = prefix + graphs.callgraph;
    cgraph.src = prefix + graphs.callgraph;
    icgraph_link.href = prefix + graphs.inverse_callgraph;
    icgraph.src = prefix + graphs.inverse_callgraph;
}

const loop_table = hints_container.querySelector(".loop-unwinding > .table");

async function refresh_loop_unwinding(loops) {
    let html = `
        <li class="table-item">
            <h4 class="width-50">Name</h4>
            <h4 class="width-50">File/Line</h4>
        </li>\n`;

    if (loops.error_code) {
        html += `
            <li class="table-item-empty danger">
                <h4>Filed to load table</h4>
                <p>Error: ${loops.detail}</p>
            </li>\n`;

        loop_table.innerHTML = html;
        return;
    }

    for (const loop of loops) {
        html += `
            <li class="table-item">
                <div class="width-50">${loop.name}</div>
                <div class="width-50">${loop.file}:${loop.line}</div>
            </li>\n`;
    }

    loop_table.innerHTML = html;
}

document.addEventListener("DOMContentLoaded", function () {
    NiceSelect.bind(document.querySelector("select"), {
        searchable: true,
        searchtext: "Search",
        placeholder: "Select a proof",
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
            response = await fetch(`api/v1/files/${encodeURIComponent(confirm_delete_entry_modal.returnValue)}`, {
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
