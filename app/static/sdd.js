const { pdfjsLib } = globalThis;

document.addEventListener("DOMContentLoaded", async () => {
    NiceSelect.bind(document.querySelector("select"), { searchable: false });
    await load_document();
});

let PDF_LOADED = false;
pdfjsLib.GlobalWorkerOptions.workerSrc = `${APP_PATH}static/pdfjs/pdf.worker.min.js`;

const container = document.querySelector(".pdf-viewer-container");
const eventBus = new pdfjsViewer.EventBus();

// enable hyperlinks within PDF files.
const linkService = new pdfjsViewer.PDFLinkService({ eventBus });
const findController = new pdfjsViewer.PDFFindController({ linkService, eventBus });

const pdfViewer = new pdfjsViewer.PDFViewer({
    container,
    eventBus,
    linkService,
    findController,
});
linkService.setViewer(pdfViewer);

// setup pdf viewer events
eventBus.on("pagesinit", () => {
    PDF_LOADED = true;
    pdfViewer.currentScaleValue = "page-fit";
});

const page_count = document.querySelector("#page-count");
const page_number = document.querySelector("#page-num");
const sel_zoom = document.querySelector("#sel-zoom");

eventBus.on("pagechanging", ({ pageNumber }) => {
    page_number.value = pageNumber;
});

let pdf;
async function load_document() {
    // Load document.
    // TODO: handle error if no pdf is available
    pdf = await pdfjsLib.getDocument(`${APP_PATH}api/v1/sdd`).promise;
    pdfViewer.setDocument(pdf);
    linkService.setDocument(pdf, null);

    page_count.textContent = pdf.numPages;
}

async function set_zoom() {
    if (!PDF_LOADED) return;
    pdfViewer.currentScaleValue = sel_zoom.value;
}

async function zoom_in() {
    if (!PDF_LOADED) return;
    pdfViewer.increaseScale();
    // TODO: Update Select Value
}

async function zoom_out() {
    if (!PDF_LOADED) return;
    pdfViewer.decreaseScale();
    // TODO: Update Select Value
}

async function set_page_number(event) {
    if (!PDF_LOADED) return;

    if (event.key == "Enter") {
        const page = Math.min(page_number.value, pdf.numPages);
        pdfViewer.currentPageNumber = page;
    }
}

async function next_page() {
    if (!PDF_LOADED) return;
    pdfViewer.nextPage();
}

async function prev_page() {
    if (!PDF_LOADED) return;
    pdfViewer.previousPage();
}

//---------------------------------------------------------------------------------------------------------
// Search
//---------------------------------------------------------------------------------------------------------

const search_input = document.querySelector("#search");
let search_type = null;

function reset_search() {
    search_type = null;
}

function find_next(event) {
    if (!PDF_LOADED) return;
    if (event.key != "Enter") return;

    if (event.shiftKey) {
        eventBus.dispatch("find", {
            type: search_type,
            caseSensitive: false,
            findPrevious: true,
            highlightAll: true,
            phraseSearch: true,
            query: search_input.value,
        });
    } else {
        eventBus.dispatch("find", {
            type: search_type,
            caseSensitive: false,
            findPrevious: false,
            highlightAll: true,
            phraseSearch: true,
            query: search_input.value,
        });
    }

    search_type = "again";
}

document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.key == "f") {
        event.preventDefault();
        search_input.focus();
    }
});
