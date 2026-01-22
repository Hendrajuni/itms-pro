/* dashboard_charts.js */

// Helper: Get Theme Colors
function getThemeColors() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
        textColor: isDark ? '#cbd5e1' : '#64748b',  // Slate-400 vs Slate-500
        gridColor: isDark ? '#334155' : '#e2e8f0',  // Slate-700 vs Slate-200
        tooltipBg: isDark ? '#1e293b' : '#ffffff',
        tooltipText: isDark ? '#f8fafc' : '#0f172a'
    };
}

// Global Chart Instaces (to allow updates)
let chartTicketCategories = null;
let chartAssetDistribution = null;
let chartTicketTrend = null;

// Common Options Factory
function getChartOptions(type) {
    const theme = getThemeColors();
    const common = {
        responsive: true,
        plugins: {
            legend: { labels: { color: theme.textColor } }
        }
    };

    if (type === 'doughnut') return common;

    return {
        ...common,
        scales: {
            x: {
                grid: { color: theme.gridColor },
                ticks: { color: theme.textColor }
            },
            y: {
                grid: { color: theme.gridColor },
                ticks: { color: theme.textColor },
                beginAtZero: true
            }
        }
    };
}

// Generic Render Function
async function renderChart(elementId, type, url, label) {
    const ctx = document.getElementById(elementId);
    if (!ctx) return null; // Element might not exist

    try {
        const response = await fetch(url);
        const data = await response.json();

        const config = {
            type: type,
            data: {
                labels: data.labels,
                datasets: [{
                    label: label,
                    data: data.data,
                    backgroundColor: [
                        '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'
                    ],
                    borderColor: type === 'line' ? '#3b82f6' : 'transparent',
                    tension: 0.4,
                    fill: type === 'line' ? true : false
                }]
            },
            options: getChartOptions(type)
        };

        // Specific tweak for Line Chart gradient
        if (type === 'line') {
            const context = ctx.getContext('2d');
            const gradient = context.createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, 'rgba(59, 130, 246, 0.3)');
            gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');
            config.data.datasets[0].backgroundColor = gradient;
        }

        return new Chart(ctx, config);

    } catch (error) {
        console.error(`Error loading chart for ${elementId}:`, error);
        return null;
    }
}

// Update Charts on Theme Toggle
function updateChartsTheme() {
    const theme = getThemeColors();
    const charts = [chartTicketCategories, chartAssetDistribution, chartTicketTrend];

    charts.forEach(chart => {
        if (!chart) return;

        // Update Legend
        if (chart.options.plugins && chart.options.plugins.legend) {
            chart.options.plugins.legend.labels.color = theme.textColor;
        }

        // Update Scales (if they exist)
        if (chart.options.scales) {
            ['x', 'y'].forEach(axis => {
                if (chart.options.scales[axis]) {
                    chart.options.scales[axis].grid.color = theme.gridColor;
                    chart.options.scales[axis].ticks.color = theme.textColor;
                }
            });
        }
        chart.update();
    });
}

// Init
document.addEventListener('DOMContentLoaded', async function () {
    chartTicketCategories = await renderChart('chartTicketCategories', 'doughnut', '/api/chart/ticket-categories/', 'Tickets');
    chartAssetDistribution = await renderChart('chartAssetDistribution', 'bar', '/api/chart/asset-distribution/', 'Assets');
    chartTicketTrend = await renderChart('chartTicketTrend', 'line', '/api/chart/tickets-monthly/', 'Tickets Trend');

    // Hook into Theme Toggle (Observer for data-theme attribute)
    const observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            if (mutation.type == "attributes" && mutation.attributeName == "data-theme") {
                updateChartsTheme();
            }
        });
    });
    observer.observe(document.documentElement, { attributes: true });
});
