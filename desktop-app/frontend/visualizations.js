
/**
 * Certify Intel - Visualization Module
 * Handles rendering of charts and widgets for new data sources.
 * Matches Certify Health branding: #3A95ED (Primary), #122753 (Navy)
 */

const BrandColors = {
    primary: '#3A95ED',
    secondary: '#122753',
    success: '#28A745',
    warning: '#FFC107',
    danger: '#DC3545',
    text: '#465D8B',
    grid: '#E2E8F0'
};

const Visualizations = {

    /**
     * Renders Crunchbase Funding Timeline
     * @param {string} elementId - Canvas ID
     * @param {Array} fundingRounds - Array of funding objects
     */
    renderFundingTimeline: (elementId, fundingRounds) => {
        const ctx = document.getElementById(elementId).getContext('2d');

        // Sort rounds by date
        const sortedRounds = fundingRounds.sort((a, b) => new Date(a.date) - new Date(b.date));

        const labels = sortedRounds.map(r => r.date);
        const amounts = sortedRounds.map(r => r.amount / 1000000); // Convert to Millions

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Funding Amount ($M)',
                    data: amounts,
                    borderColor: BrandColors.primary,
                    backgroundColor: 'rgba(58, 149, 237, 0.1)',
                    borderWidth: 2,
                    pointBackgroundColor: BrandColors.secondary,
                    pointRadius: 4,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return `$${context.raw}M - ${sortedRounds[context.dataIndex].type}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: BrandColors.grid },
                        title: { display: true, text: 'USD Millions' }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    },

    /**
     * Renders Glassdoor Employee Sentiment Gauge
     * @param {string} elementId - Canvas ID
     * @param {number} rating - Score 0-5
     */
    renderSentimentGauge: (elementId, rating) => {
        const ctx = document.getElementById(elementId).getContext('2d');
        const percentage = (rating / 5) * 100;

        // Determine color based on score
        let color = BrandColors.danger;
        if (rating >= 3) color = BrandColors.warning;
        if (rating >= 4) color = BrandColors.success;
        if (rating >= 4.5) color = BrandColors.primary;

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Score', 'Remaining'],
                datasets: [{
                    data: [rating, 5 - rating],
                    backgroundColor: [color, BrandColors.grid],
                    borderWidth: 0,
                    cutout: '75%'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                }
            },
            plugins: [{
                id: 'textCenter',
                beforeDraw: function (chart) {
                    var width = chart.width,
                        height = chart.height,
                        ctx = chart.ctx;

                    ctx.restore();
                    var fontSize = (height / 100).toFixed(2);
                    ctx.font = "bold " + fontSize + "em Poppins";
                    ctx.textBaseline = "middle";
                    ctx.fillStyle = BrandColors.secondary;

                    var text = rating.toFixed(1),
                        textX = Math.round((width - ctx.measureText(text).width) / 2),
                        textY = height / 2;

                    ctx.fillText(text, textX, textY);
                    ctx.save();
                }
            }]
        });
    },

    /**
     * Renders Hiring Trend Chart (Indeed/Zip)
     * @param {string} elementId 
     * @param {Array} history - Array of {date, count}
     */
    renderHiringTrend: (elementId, history) => {
        const ctx = document.getElementById(elementId).getContext('2d');

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: history.map(h => h.date),
                datasets: [{
                    label: 'Active Job Postings',
                    data: history.map(h => h.count),
                    backgroundColor: BrandColors.navy_dark || '#122753',
                    borderRadius: 3
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { display: false }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    },

    /**
     * Renders Innovation Radar (USPTO Patents)
     * @param {string} elementId 
     * @param {Object} categories - Map of category -> count
     */
    renderInnovationRadar: (elementId, categories) => {
        const ctx = document.getElementById(elementId).getContext('2d');

        new Chart(ctx, {
            type: 'radar',
            data: {
                labels: Object.keys(categories),
                datasets: [{
                    label: 'Patent Focus Areas',
                    data: Object.values(categories),
                    fill: true,
                    backgroundColor: 'rgba(58, 149, 237, 0.2)',
                    borderColor: BrandColors.primary,
                    pointBackgroundColor: BrandColors.primary,
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: BrandColors.primary
                }]
            },
            options: {
                elements: {
                    line: { borderWidth: 3 }
                },
                scales: {
                    r: {
                        angleLines: { color: BrandColors.grid },
                        grid: { color: BrandColors.grid },
                        pointLabels: {
                            font: { family: 'Poppins', size: 11 }
                        }
                    }
                }
            }
        });
    },

    /**
     * Renders Competitive Positioning Matrix (Bubble Chart)
     * @param {string} elementId 
     * @param {Array} data - Array of {x, y, r, label}
     * @param {string} xLabel 
     * @param {string} yLabel 
     */
    renderPositioningMatrix: (elementId, data, xLabel, yLabel) => {
        const ctx = document.getElementById(elementId).getContext('2d');

        // Destroy existing if needed (handled by caller ideally, but safety check)
        const existingChart = Chart.getChart(elementId);
        if (existingChart) existingChart.destroy();

        new Chart(ctx, {
            type: 'bubble',
            data: {
                datasets: [{
                    label: 'Competitors',
                    data: data,
                    backgroundColor: data.map(d => d.color || 'rgba(58, 149, 237, 0.6)'),
                    borderColor: data.map(d => d.borderColor || '#fff'),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return `${context.raw.label}: (${xLabel}: ${context.raw.x}, ${yLabel}: ${context.raw.y})`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: { display: true, text: xLabel },
                        grid: { color: BrandColors.grid }
                    },
                    y: {
                        title: { display: true, text: yLabel },
                        grid: { color: BrandColors.grid }
                    }
                }
            }
        });
    }
};

// Expose to global scope
window.Visualizations = Visualizations;
