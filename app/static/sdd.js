const { pdfjsLib } = globalThis;

let PDF_LOADED = false;
pdfjsLib.GlobalWorkerOptions.workerSrc = "static/pdfjs/pdf.worker.min.js";

const container = document.querySelector("#viewerContainer");
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
    pdfViewer.currentScaleValue = "page-width";
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

async function mapPdfOutlineToPages(outline, pdf) {
    const pairs = [];
    if (!outline) return pairs;

    for (let o of outline) {
        const ref = o.dest[0];
        const page_idx = await pdf.getPageIndex(ref);
        pairs.push({ title: o.title, page_number: parseInt(page_idx) + 1, dest: o.dest });

        if (o.items) {
            pairs.push(...(await mapPdfOutlineToPages(o.items)));
        }
    }

    return pairs;
}

async function load_document() {
    // Load document.
    const pdf = await pdfjsLib.getDocument("static/CaSSIS-FSW-DDD_v3.pdf").promise;
    pdfViewer.setDocument(pdf);
    pdfLinkService.setDocument(pdf, null);

    // get document outline
    const outline = await mapPdfOutlineToPages(await pdf.getOutline(), pdf);
}

document.addEventListener("DOMContentLoaded", load_document);
