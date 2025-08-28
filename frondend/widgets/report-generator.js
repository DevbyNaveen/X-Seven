/**
 * Report Generator Widget
 * Generates downloadable reports in various formats
 */

class ReportGeneratorWidget extends BaseWidget {
    constructor() {
        super('report-generator', 'Report Generator');
        this.generating = false;
    }

    renderContent() {
        return `
            <div class="space-y-4">
                <div class="grid grid-cols-2 gap-3">
                    <button id="daily-sales-report" class="w-full bg-blue-600 text-white py-2 px-3 rounded text-sm hover:bg-blue-700">
                        Daily Sales Summary
                    </button>
                    <button id="menu-performance-report" class="w-full bg-green-600 text-white py-2 px-3 rounded text-sm hover:bg-green-700">
                        Menu Performance
                    </button>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <button id="customer-analytics-report" class="w-full bg-purple-600 text-white py-2 px-3 rounded text-sm hover:bg-purple-700">
                        Customer Analytics
                    </button>
                    <button id="staff-productivity-report" class="w-full bg-orange-600 text-white py-2 px-3 rounded text-sm hover:bg-orange-700">
                        Staff Reports
                    </button>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <button id="inventory-report" class="w-full bg-teal-600 text-white py-2 px-3 rounded text-sm hover:bg-teal-700">
                        Inventory Analysis
                    </button>
                    <button id="qr-codes-batch" class="w-full bg-indigo-600 text-white py-2 px-3 rounded text-sm hover:bg-indigo-700">
                        QR Code Batch
                    </button>
                </div>
                
                <div id="report-status" class="text-sm text-gray-600 text-center py-2">
                    Select a report to generate
                </div>
                
                <div id="recent-reports" class="border-t pt-3">
                    <h4 class="text-sm font-medium text-gray-900 mb-2">Recent Reports</h4>
                    <div id="recent-reports-list" class="space-y-1 text-sm">
                        <!-- Recent reports will be listed here -->
                    </div>
                </div>
            </div>
        `;
    }

    async updateData() {
        this.setupEventListeners();
        this.loadRecentReports();
    }

    setupEventListeners() {
        document.getElementById('daily-sales-report')?.addEventListener('click', () => {
            this.generateReport('daily-sales', 'pdf');
        });
        
        document.getElementById('menu-performance-report')?.addEventListener('click', () => {
            this.generateReport('menu-performance', 'excel');
        });
        
        document.getElementById('customer-analytics-report')?.addEventListener('click', () => {
            this.generateReport('customer-analytics', 'csv');
        });
        
        document.getElementById('staff-productivity-report')?.addEventListener('click', () => {
            this.generateReport('staff-productivity', 'pdf');
        });
        
        document.getElementById('inventory-report')?.addEventListener('click', () => {
            this.generateReport('inventory-analysis', 'excel');
        });
        
        document.getElementById('qr-codes-batch')?.addEventListener('click', () => {
            this.generateQRCodes();
        });
    }

    async generateReport(type, format) {
        if (this.generating) return;
        
        this.generating = true;
        const statusEl = document.getElementById('report-status');
        statusEl.textContent = 'Generating report...';
        statusEl.className = 'text-sm text-blue-600 text-center py-2';

        try {
            const response = await fetch('/api/v1/reports/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    business_id: this.dashboard.businessId,
                    report_type: type,
                    format: format,
                    date_range: this.getDateRange()
                })
            });

            const result = await response.json();
            
            if (result.success) {
                this.downloadFile(result.download_url, result.filename);
                this.addToRecentReports(result.filename, type, format);
                statusEl.textContent = 'Report generated successfully!';
                statusEl.className = 'text-sm text-green-600 text-center py-2';
            } else {
                throw new Error(result.error || 'Failed to generate report');
            }
        } catch (error) {
            statusEl.textContent = `Error: ${error.message}`;
            statusEl.className = 'text-sm text-red-600 text-center py-2';
        } finally {
            this.generating = false;
            setTimeout(() => {
                statusEl.textContent = 'Select a report to generate';
                statusEl.className = 'text-sm text-gray-600 text-center py-2';
            }, 3000);
        }
    }

    async generateQRCodes() {
        const statusEl = document.getElementById('report-status');
        statusEl.textContent = 'Generating QR codes...';
        
        try {
            const response = await fetch('/api/v1/qr-codes/generate-batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    business_id: this.dashboard.businessId,
                    table_count: 20, // Default to 20 tables
                    format: 'zip'
                })
            });

            const result = await response.json();
            
            if (result.success) {
                this.downloadFile(result.download_url, 'qr-codes.zip');
                statusEl.textContent = 'QR codes generated successfully!';
            }
        } catch (error) {
            statusEl.textContent = 'Error generating QR codes';
        }
    }

    downloadFile(url, filename) {
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    getDateRange() {
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - 7); // Default to last 7 days
        
        return {
            start: startDate.toISOString().split('T')[0],
            end: endDate.toISOString().split('T')[0]
        };
    }

    addToRecentReports(filename, type, format) {
        const reports = this.getRecentReports();
        reports.unshift({
            filename,
            type,
            format,
            date: new Date().toLocaleString()
        });
        
        // Keep only last 10 reports
        reports.splice(10);
        localStorage.setItem('recent-reports', JSON.stringify(reports));
        
        this.loadRecentReports();
    }

    getRecentReports() {
        const stored = localStorage.getItem('recent-reports');
        return stored ? JSON.parse(stored) : [];
    }

    loadRecentReports() {
        const reports = this.getRecentReports();
        const container = document.getElementById('recent-reports-list');
        
        if (!container) return;
        
        if (reports.length === 0) {
            container.innerHTML = '<div class="text-gray-500 text-xs">No recent reports</div>';
            return;
        }
        
        container.innerHTML = reports.map(report => `
            <div class="flex justify-between items-center py-1 border-b border-gray-100 last:border-0">
                <span class="text-xs text-gray-600">${report.type} (${report.format})</span>
                <span class="text-xs text-gray-400">${report.date}</span>
            </div>
        `).join('');
    }
}

// Download Center Widget
class DownloadCenterWidget extends BaseWidget {
    constructor() {
        super('download-center', 'Download Center');
    }

    renderContent() {
        return `
            <div class="space-y-3">
                <div class="grid grid-cols-1 gap-2">
                    <button id="download-qr-all" class="w-full bg-gray-600 text-white py-2 px-3 rounded text-sm hover:bg-gray-700">
                        All QR Codes (ZIP)
                    </button>
                    <button id="download-menu-pdf" class="w-full bg-gray-600 text-white py-2 px-3 rounded text-sm hover:bg-gray-700">
                        Menu PDF
                    </button>
                    <button id="download-sales-csv" class="w-full bg-gray-600 text-white py-2 px-3 rounded text-sm hover:bg-gray-700">
                        Sales Data (CSV)
                    </button>
                    <button id="download-customer-export" class="w-full bg-gray-600 text-white py-2 px-3 rounded text-sm hover:bg-gray-700">
                        Customer Export
                    </button>
                    <button id="download-marketing-templates" class="w-full bg-gray-600 text-white py-2 px-3 rounded text-sm hover:bg-gray-700">
                        Marketing Templates
                    </button>
                </div>
                
                <div class="border-t pt-3">
                    <h4 class="text-sm font-medium text-gray-900 mb-2">Quick Exports</h4>
                    <div class="space-y-2">
                        <label class="flex items-center text-sm">
                            <input type="checkbox" id="export-customers" class="mr-2" checked>
                            Customer data
                        </label>
                        <label class="flex items-center text-sm">
                            <input type="checkbox" id="export-orders" class="mr-2" checked>
                            Order history
                        </label>
                        <label class="flex items-center text-sm">
                            <input type="checkbox" id="export-menu" class="mr-2" checked>
                            Menu items
                        </label>
                        <label class="flex items-center text-sm">
                            <input type="checkbox" id="export-analytics" class="mr-2">
                            Analytics data
                        </label>
                    </div>
                    <button id="export-selected" class="w-full mt-2 bg-blue-600 text-white py-2 px-3 rounded text-sm hover:bg-blue-700">
                        Export Selected
                    </button>
                </div>
            </div>
        `;
    }

    async updateData() {
        this.setupDownloadListeners();
    }

    setupDownloadListeners() {
        document.getElementById('download-qr-all')?.addEventListener('click', () => {
            this.downloadFile('qr-codes-all', 'zip');
        });
        
        document.getElementById('download-menu-pdf')?.addEventListener('click', () => {
            this.downloadFile('menu-pdf', 'pdf');
        });
        
        document.getElementById('download-sales-csv')?.addEventListener('click', () => {
            this.downloadFile('sales-csv', 'csv');
        });
        
        document.getElementById('download-customer-export')?.addEventListener('click', () => {
            this.downloadFile('customer-export', 'csv');
        });
        
        document.getElementById('download-marketing-templates')?.addEventListener('click', () => {
            this.downloadFile('marketing-templates', 'zip');
        });
        
        document.getElementById('export-selected')?.addEventListener('click', () => {
            this.exportSelectedData();
        });
    }

    async exportSelectedData() {
        const selected = {
            customers: document.getElementById('export-customers')?.checked,
            orders: document.getElementById('export-orders')?.checked,
            menu: document.getElementById('export-menu')?.checked,
            analytics: document.getElementById('export-analytics')?.checked
        };

        try {
            const response = await fetch('/api/v1/export/custom', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    business_id: this.dashboard.businessId,
                    export_types: selected,
                    format: 'zip'
                })
            });

            const result = await response.json();
            if (result.success) {
                this.downloadFile(result.download_url, 'business-export.zip');
            }
        } catch (error) {
            console.error('Export error:', error);
        }
    }

    async downloadFile(type, format) {
        try {
            const response = await fetch('/api/v1/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    business_id: this.dashboard.businessId,
                    type,
                    format
                })
            });

            const result = await response.json();
            if (result.success) {
                const link = document.createElement('a');
                link.href = result.download_url;
                link.download = result.filename;
                link.click();
            }
        } catch (error) {
            console.error('Download error:', error);
        }
    }
}

// Export all widgets
window.ReportGeneratorWidget = ReportGeneratorWidget;
window.DownloadCenterWidget = DownloadCenterWidget;
