/**
 * Discovery Network Graph - Interactive visualization of musical evolution
 */

class DiscoveryNetwork {
    constructor(containerId) {
        this.container = d3.select(`#${containerId}`);
        this.width = this.container.node().getBoundingClientRect().width;
        this.height = 600;
        
        this.svg = null;
        this.simulation = null;
        this.nodes = [];
        this.links = [];
        this.selectedNode = null;
        
        // Scales
        this.colorScale = d3.scaleOrdinal(d3.schemeCategory10);
        this.sizeScale = d3.scaleSqrt().range([5, 30]);
        
        this.init();
    }
    
    init() {
        // Create SVG
        this.svg = this.container
            .append('svg')
            .attr('width', this.width)
            .attr('height', this.height);
        
        // Add container groups
        this.g = this.svg.append('g');
        
        // Add zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });
        
        this.svg.call(zoom);
        
        // Add arrow markers for directed edges
        this.svg.append('defs').selectAll('marker')
            .data(['discovery', 'session'])
            .enter().append('marker')
            .attr('id', d => `arrow-${d}`)
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 20)
            .attr('refY', 0)
            .attr('markerWidth', 8)
            .attr('markerHeight', 8)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', d => d === 'discovery' ? '#1db954' : '#1ed760');
        
        // Create force simulation
        this.simulation = d3.forceSimulation()
            .force('link', d3.forceLink().id(d => d.id).distance(100))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide().radius(d => this.sizeScale(d.play_count) + 5));
        
        // Add controls
        this.createControls();
        
        // Add tooltip
        this.tooltip = d3.select('body').append('div')
            .attr('class', 'network-tooltip')
            .style('opacity', 0)
            .style('position', 'absolute')
            .style('background', 'rgba(0, 0, 0, 0.9)')
            .style('color', 'white')
            .style('padding', '10px')
            .style('border-radius', '5px')
            .style('font-size', '12px')
            .style('pointer-events', 'none');
    }
    
    createControls() {
        const controls = this.container
            .append('div')
            .attr('class', 'network-controls')
            .style('position', 'absolute')
            .style('top', '10px')
            .style('right', '10px')
            .style('background', 'rgba(40, 40, 40, 0.9)')
            .style('padding', '10px')
            .style('border-radius', '5px');
        
        // Layout selector
        controls.append('label')
            .text('Layout: ')
            .style('color', '#b3b3b3')
            .style('margin-right', '5px');
        
        controls.append('select')
            .attr('id', 'layout-select')
            .on('change', (event) => this.changeLayout(event.target.value))
            .selectAll('option')
            .data(['force', 'radial', 'timeline'])
            .enter().append('option')
            .text(d => d.charAt(0).toUpperCase() + d.slice(1))
            .attr('value', d => d);
        
        // Filter by importance
        controls.append('div')
            .style('margin-top', '10px')
            .append('label')
            .text('Min. Importance: ')
            .style('color', '#b3b3b3');
        
        controls.append('input')
            .attr('type', 'range')
            .attr('min', '0')
            .attr('max', '1')
            .attr('step', '0.1')
            .attr('value', '0')
            .style('width', '100px')
            .on('input', (event) => this.filterByImportance(+event.target.value));
    }
    
    async loadData() {
        try {
            const response = await fetch('/api/visualizations/discovery-network');
            const data = await response.json();
            
            this.processData(data);
            this.render();
            
            // Show stats
            this.displayStats(data.stats);
            
        } catch (error) {
            console.error('Error loading network data:', error);
        }
    }
    
    processData(data) {
        this.nodes = data.nodes;
        this.links = data.edges;
        
        // Set up scales
        const playExtent = d3.extent(this.nodes, d => d.play_count);
        this.sizeScale.domain(playExtent);
        
        // Add discovery order for timeline layout
        this.nodes.forEach((node, i) => {
            node.discoveryOrder = i;
            node.x = this.width / 2;
            node.y = this.height / 2;
        });
    }
    
    render() {
        // Clear previous elements
        this.g.selectAll('*').remove();
        
        // Create link elements
        const link = this.g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(this.links)
            .enter().append('line')
            .attr('stroke', d => d.type === 'discovery' ? '#1db954' : '#1ed760')
            .attr('stroke-opacity', d => Math.min(0.6, d.weight))
            .attr('stroke-width', d => Math.max(1, d.weight * 3))
            .attr('marker-end', d => `url(#arrow-${d.type})`);
        
        // Create node elements
        const node = this.g.append('g')
            .attr('class', 'nodes')
            .selectAll('g')
            .data(this.nodes)
            .enter().append('g')
            .attr('class', 'node')
            .call(this.drag());
        
        // Add circles
        node.append('circle')
            .attr('r', d => this.sizeScale(d.play_count))
            .attr('fill', d => this.colorScale(d.importance))
            .attr('stroke', '#fff')
            .attr('stroke-width', 2)
            .style('cursor', 'pointer')
            .on('mouseover', (event, d) => this.showTooltip(event, d))
            .on('mouseout', () => this.hideTooltip())
            .on('click', (event, d) => this.selectNode(d));
        
        // Add labels for important nodes
        node.filter(d => d.importance > 0.5)
            .append('text')
            .text(d => d.name)
            .attr('x', 0)
            .attr('y', d => this.sizeScale(d.play_count) + 15)
            .attr('text-anchor', 'middle')
            .attr('fill', '#ffffff')
            .style('font-size', '12px')
            .style('pointer-events', 'none');
        
        // Update simulation
        this.simulation
            .nodes(this.nodes)
            .on('tick', () => this.ticked(link, node));
        
        this.simulation.force('link')
            .links(this.links);
        
        // Restart simulation
        this.simulation.alpha(1).restart();
    }
    
    ticked(link, node) {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        node
            .attr('transform', d => `translate(${d.x},${d.y})`);
    }
    
    drag() {
        return d3.drag()
            .on('start', (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on('drag', (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on('end', (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            });
    }
    
    showTooltip(event, d) {
        const formatDate = d3.timeFormat('%B %d, %Y');
        const discovered = new Date(d.discovered);
        
        this.tooltip
            .style('opacity', 1)
            .html(`
                <strong>${d.name}</strong><br>
                Discovered: ${formatDate(discovered)}<br>
                First track: ${d.first_track}<br>
                Total plays: ${d.play_count}<br>
                Active for: ${d.days_active} days<br>
                Play density: ${d.play_density} plays/day
            `)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 10) + 'px');
    }
    
    hideTooltip() {
        this.tooltip.style('opacity', 0);
    }
    
    selectNode(node) {
        this.selectedNode = node;
        
        // Highlight connected nodes
        const connectedNodes = new Set([node.id]);
        this.links.forEach(link => {
            if (link.source.id === node.id) connectedNodes.add(link.target.id);
            if (link.target.id === node.id) connectedNodes.add(link.source.id);
        });
        
        // Update node opacity
        this.g.selectAll('.node circle')
            .style('opacity', d => connectedNodes.has(d.id) ? 1 : 0.2);
        
        // Update link opacity
        this.g.selectAll('.links line')
            .style('opacity', d => 
                (d.source.id === node.id || d.target.id === node.id) ? 1 : 0.1
            );
        
        // Emit event
        const event = new CustomEvent('nodeSelected', { detail: node });
        this.container.node().dispatchEvent(event);
    }
    
    changeLayout(layoutType) {
        switch (layoutType) {
            case 'radial':
                this.applyRadialLayout();
                break;
            case 'timeline':
                this.applyTimelineLayout();
                break;
            default:
                // Reset to force layout
                this.nodes.forEach(node => {
                    node.fx = null;
                    node.fy = null;
                });
                this.simulation.alpha(1).restart();
        }
    }
    
    applyRadialLayout() {
        const centerX = this.width / 2;
        const centerY = this.height / 2;
        const radius = Math.min(centerX, centerY) - 100;
        
        // Sort nodes by discovery date
        const sortedNodes = [...this.nodes].sort((a, b) => 
            new Date(a.discovered) - new Date(b.discovered)
        );
        
        sortedNodes.forEach((node, i) => {
            const angle = (i / sortedNodes.length) * 2 * Math.PI;
            node.fx = centerX + radius * Math.cos(angle);
            node.fy = centerY + radius * Math.sin(angle);
        });
        
        this.simulation.alpha(0.5).restart();
    }
    
    applyTimelineLayout() {
        const margin = 50;
        const timeExtent = d3.extent(this.nodes, d => new Date(d.discovered));
        const timeScale = d3.scaleTime()
            .domain(timeExtent)
            .range([margin, this.width - margin]);
        
        // Group by month
        const monthGroups = d3.group(this.nodes, d => 
            d3.timeFormat('%Y-%m')(new Date(d.discovered))
        );
        
        let yOffset = margin;
        monthGroups.forEach((nodes, month) => {
            nodes.forEach((node, i) => {
                node.fx = timeScale(new Date(node.discovered));
                node.fy = yOffset + (i * 40);
            });
            yOffset += (nodes.length * 40) + 20;
        });
        
        this.simulation.alpha(0.5).restart();
    }
    
    filterByImportance(minImportance) {
        // Filter nodes
        const filteredNodes = this.nodes.filter(d => d.importance >= minImportance);
        const filteredNodeIds = new Set(filteredNodes.map(d => d.id));
        
        // Filter links
        const filteredLinks = this.links.filter(d => 
            filteredNodeIds.has(d.source.id || d.source) && 
            filteredNodeIds.has(d.target.id || d.target)
        );
        
        // Update visualization
        this.g.selectAll('.node')
            .style('display', d => filteredNodeIds.has(d.id) ? null : 'none');
        
        this.g.selectAll('.links line')
            .style('display', d => 
                filteredNodeIds.has(d.source.id) && filteredNodeIds.has(d.target.id) ? null : 'none'
            );
    }
    
    displayStats(stats) {
        const statsContainer = this.container
            .append('div')
            .attr('class', 'network-stats')
            .style('position', 'absolute')
            .style('bottom', '10px')
            .style('left', '10px')
            .style('background', 'rgba(40, 40, 40, 0.9)')
            .style('padding', '15px')
            .style('border-radius', '5px')
            .style('color', '#b3b3b3')
            .style('font-size', '14px');
        
        statsContainer.html(`
            <strong style="color: #1db954;">Network Statistics</strong><br>
            Artists: ${stats.total_artists}<br>
            Connections: ${stats.total_connections}<br>
            Network Density: ${(stats.network_density * 100).toFixed(1)}%<br>
            Exploration Score: ${stats.exploration_score}%<br>
            Discovery Trend: ${stats.discovery_rate.trend}
        `);
        
        // Add discovery hubs if available
        if (stats.discovery_hubs && stats.discovery_hubs.length > 0) {
            statsContainer.append('div')
                .style('margin-top', '10px')
                .html(`<strong>Discovery Hubs:</strong><br>` +
                    stats.discovery_hubs.map(hub => 
                        `${hub.artist} (${(hub.centrality * 100).toFixed(1)}%)`
                    ).join('<br>')
                );
        }
    }
    
    async findPath(artist1, artist2) {
        try {
            const response = await fetch(`/api/visualizations/discovery-path/${artist1}/${artist2}`);
            const data = await response.json();
            
            if (data.path) {
                this.highlightPath(data.path);
            }
        } catch (error) {
            console.error('Error finding path:', error);
        }
    }
    
    highlightPath(path) {
        const pathIds = new Set(path.map(p => p.id));
        
        // Highlight nodes in path
        this.g.selectAll('.node circle')
            .style('stroke', d => pathIds.has(d.id) ? '#1db954' : '#fff')
            .style('stroke-width', d => pathIds.has(d.id) ? 4 : 2);
        
        // Highlight links in path
        this.g.selectAll('.links line')
            .style('stroke-width', d => {
                const inPath = pathIds.has(d.source.id) && pathIds.has(d.target.id);
                return inPath ? 5 : Math.max(1, d.weight * 3);
            })
            .style('stroke', d => {
                const inPath = pathIds.has(d.source.id) && pathIds.has(d.target.id);
                return inPath ? '#1db954' : (d.type === 'discovery' ? '#1db954' : '#1ed760');
            });
    }
}

// Export for use
window.DiscoveryNetwork = DiscoveryNetwork;