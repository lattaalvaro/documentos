var currentPDF = null;
var currentPage = 1;
var pdfDoc = null;
var totalPages = 0;

// Abrir el modal con el documento PDF
function openModal(pdfURL) {
    document.getElementById('pdfModal').style.display = "block";
    currentPDF = pdfURL;
    loadPDF(pdfURL);
}

// Cargar el archivo PDF en el visor
function loadPDF(url) {
    pdfjsLib.getDocument(url).promise.then(function (doc) {
        pdfDoc = doc;
        totalPages = pdfDoc.numPages;
        renderPage(currentPage);
    });
}

// Renderizar la página del PDF
function renderPage(pageNum) {
    pdfDoc.getPage(pageNum).then(function (page) {
        var scale = 1.5;
        var viewport = page.getViewport({ scale: scale });
        var canvas = document.getElementById('pdfCanvas');
        var ctx = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        var renderContext = {
            canvasContext: ctx,
            viewport: viewport
        };

        page.render(renderContext);
    });
}

// Navegar a la página anterior o siguiente
function navigatePDF(step) {
    var newPage = currentPage + step;
    if (newPage > 0 && newPage <= totalPages) {
        currentPage = newPage;
        renderPage(currentPage);
    }
}

// Cerrar el modal
function closeModal() {
    document.getElementById('pdfModal').style.display = "none";
}




