const { pdfjsLib } = globalThis;

let PDF_LOADED = false;
pdfjsLib.GlobalWorkerOptions.workerSrc = "static/pdfjs/pdf.worker.min.js";

const container = document.querySelector(".pdf-viewer-container");
const eventBus = new pdfjsViewer.EventBus();

// enable hyperlinks within PDF files.
const pdfLinkService = new pdfjsViewer.PDFLinkService({ eventBus });

const pdfViewer = new pdfjsViewer.PDFViewer({
    container,
    eventBus,
    linkService: pdfLinkService,
});
pdfLinkService.setViewer(pdfViewer);

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

// let skipNextEvent = false;
// eventBus.on("pagechanging", ({ pageNumber }) => {
//     if (!PDF_LOADED) return;
//     if (!outline) return;

//     // update pagenumber
//     $(".intPageNumber").val(pageNumber);

//     if (skipNextEvent) {
//         skipNextEvent = false;
//         return;
//     }

//     // update chapter select (only if there's no text in the input fields)
//     if (!$("#txtComment").summernote("isEmpty") || !$("#txtReason").summernote("isEmpty")) return;

//     // get first title on current page
//     let title = outline.find(({ page_number }) => page_number == pageNumber)?.title;
//     // find previous title if the current page has no title
//     title ??= outline.filter(({ page_number }) => page_number <= pageNumber).pop()?.title;

//     if (title) {
//         const id = $('#selChapter > option[data-name="' + title + '"]').val();
//         $("#selChapter").selectpicker("val", id);
//     }
// });

// $("#selChapter").change((e) => {
//     if (!PDF_LOADED) return;
//     if (!outline) return;

//     const chapter = $("#selChapter > option:selected").text();
//     let page = outline.find(({ title }) => title == chapter);

//     if (page) {
//         skipNextEvent = true;
//         pdfViewer.scrollPageIntoView({ pageNumber: page.page_number, destArray: page.dest });
//         setTimeout(() => {
//             skipNextEvent = false;
//         }, 100);
//     }
// });

// async function mapPdfOutlineToPages(outline, pdf) {
//     const pairs = [];
//     if (!outline) return pairs;

//     for (let o of outline) {
//         const ref = o.dest[0];
//         const page_idx = await pdf.getPageIndex(ref);
//         pairs.push({ title: o.title, page_number: parseInt(page_idx) + 1, dest: o.dest });

//         if (o.items) {
//             pairs.push(...(await mapPdfOutlineToPages(o.items)));
//         }
//     }

//     return pairs;
// }

let pdf;
async function load_document() {
    // Load document.
    pdf = await pdfjsLib.getDocument("static/CaSSIS-FSW-DDD_v3.pdf").promise;
    pdfViewer.setDocument(pdf);
    pdfLinkService.setDocument(pdf, null);

    page_count.textContent = pdf.numPages;

    // get document outline
    // const outline = await mapPdfOutlineToPages(await pdf.getOutline(), pdf);
}

async function set_zoom() {
    if (!PDF_LOADED) return;
    pdfViewer.currentScaleValue = sel_zoom.value;
}

async function zoom_in() {
    if (!PDF_LOADED) return;
    pdfViewer.currentScaleValue = (parseFloat(pdfViewer.currentScaleValue) || 1) + 0.1;
    // TODO: Update Select Value
}

async function zoom_out() {
    if (!PDF_LOADED) return;
    pdfViewer.currentScaleValue = (parseFloat(pdfViewer.currentScaleValue) || 1) - 0.1;
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

document.addEventListener("DOMContentLoaded", async () => {
    NiceSelect.bind(document.querySelector("select"), { searchable: false });
    await load_document();
});
