/**
 * Certify Intel - PDF/Excel Export Engine
 * Uses jsPDF + autoTable for PDF, SheetJS for Excel.
 */
(function () {
    'use strict';

    class PDFExporter {
        constructor() {
            this.defaultOptions = {
                orientation: 'portrait',
                unit: 'mm',
                format: 'a4'
            };
        }

        _ensureLoaded() {
            if (!window.jspdf || !window.jspdf.jsPDF) {
                throw new Error('jsPDF library not loaded. Please refresh the page.');
            }
        }

        exportTable(title, headers, rows, filename) {
            this._ensureLoaded();
            filename = filename || 'export.pdf';
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF(this.defaultOptions);

            // Header
            doc.setFontSize(18);
            doc.setTextColor(18, 39, 83); // navy-dark
            doc.text(title, 14, 22);

            doc.setFontSize(10);
            doc.setTextColor(100, 100, 100);
            doc.text('Generated: ' + new Date().toLocaleDateString(), 14, 30);
            doc.text('Certify Intel', 14, 35);

            // Table
            doc.autoTable({
                head: [headers],
                body: rows,
                startY: 42,
                theme: 'striped',
                headStyles: { fillColor: [58, 149, 237] }, // primary-color
                styles: { fontSize: 9 },
            });

            doc.save(filename);
        }

        chartToImage(canvasElement) {
            if (!canvasElement) return null;
            return canvasElement.toDataURL('image/png');
        }

        exportWithCharts(title, chartCanvases, tableData, filename) {
            this._ensureLoaded();
            filename = filename || 'report.pdf';
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF({
                ...this.defaultOptions,
                orientation: 'landscape'
            });

            doc.setFontSize(20);
            doc.setTextColor(18, 39, 83);
            doc.text(title, 14, 20);

            doc.setFontSize(10);
            doc.setTextColor(100, 100, 100);
            doc.text('Generated: ' + new Date().toLocaleDateString(), 14, 28);

            let yPos = 36;

            if (chartCanvases && chartCanvases.length) {
                chartCanvases.forEach(canvas => {
                    if (!canvas) return;
                    try {
                        const imgData = this.chartToImage(canvas);
                        if (imgData) {
                            doc.addImage(imgData, 'PNG', 14, yPos, 130, 65);
                            yPos += 72;
                            if (yPos > 145) {
                                doc.addPage();
                                yPos = 20;
                            }
                        }
                    } catch (err) {
                        console.warn('[PDFExporter] Failed to capture chart:', err);
                    }
                });
            }

            if (tableData && tableData.headers && tableData.rows) {
                doc.autoTable({
                    head: [tableData.headers],
                    body: tableData.rows,
                    startY: yPos,
                    theme: 'striped',
                    headStyles: { fillColor: [58, 149, 237] },
                    styles: { fontSize: 9 },
                });
            }

            doc.save(filename);
        }
    }

    class ExcelExporter {
        _ensureLoaded() {
            if (typeof XLSX === 'undefined') {
                throw new Error('SheetJS (XLSX) library not loaded. Please refresh the page.');
            }
        }

        exportTable(title, headers, rows, filename) {
            this._ensureLoaded();
            filename = filename || 'export.xlsx';
            const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);

            // Auto-size columns
            const colWidths = headers.map((h, i) => {
                let max = String(h).length;
                rows.forEach(r => {
                    const len = String(r[i] || '').length;
                    if (len > max) max = len;
                });
                return { wch: Math.min(max + 2, 40) };
            });
            ws['!cols'] = colWidths;

            const sheetName = title.substring(0, 31).replace(/[\\/*?[\]]/g, '');
            const wb = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(wb, ws, sheetName);
            XLSX.writeFile(wb, filename);
        }

        exportMultiSheet(sheets, filename) {
            this._ensureLoaded();
            filename = filename || 'export.xlsx';
            const wb = XLSX.utils.book_new();

            sheets.forEach(({ name, headers, rows }) => {
                const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
                const sheetName = name.substring(0, 31).replace(/[\\/*?[\]]/g, '');
                XLSX.utils.book_append_sheet(wb, ws, sheetName);
            });

            XLSX.writeFile(wb, filename);
        }
    }

    // Expose globally
    window.PDFExporter = PDFExporter;
    window.ExcelExporter = ExcelExporter;
    window.pdfExporter = new PDFExporter();
    window.excelExporter = new ExcelExporter();
})();
