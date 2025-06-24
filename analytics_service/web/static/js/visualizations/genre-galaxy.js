/**
 * Genre Galaxy Explorer - 3D visualization of musical genres
 */

class GenreGalaxy {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.genres = new Map();
        this.connections = [];
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.selectedGenre = null;
        
        this.init();
    }
    
    init() {
        // Set up Three.js scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0a0a);
        
        // Set up camera
        const aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);
        this.camera.position.set(0, 0, 200);
        
        // Set up renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.appendChild(this.renderer.domElement);
        
        // Set up controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.enableZoom = true;
        this.controls.autoRotate = true;
        this.controls.autoRotateSpeed = 0.5;
        
        // Add lights
        const ambientLight = new THREE.AmbientLight(0x404040);
        this.scene.add(ambientLight);
        
        const pointLight = new THREE.PointLight(0xffffff, 1);
        pointLight.position.set(100, 100, 100);
        this.scene.add(pointLight);
        
        // Add stars background
        this.createStarfield();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Start animation loop
        this.animate();
    }
    
    createStarfield() {
        const geometry = new THREE.BufferGeometry();
        const vertices = [];
        
        for (let i = 0; i < 5000; i++) {
            vertices.push(
                (Math.random() - 0.5) * 600,
                (Math.random() - 0.5) * 600,
                (Math.random() - 0.5) * 600
            );
        }
        
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
        
        const material = new THREE.PointsMaterial({
            color: 0xffffff,
            size: 0.5,
            transparent: true,
            opacity: 0.6
        });
        
        const stars = new THREE.Points(geometry, material);
        this.scene.add(stars);
    }
    
    async loadData() {
        try {
            const response = await fetch('/api/visualizations/genre-galaxy');
            const data = await response.json();
            
            this.createGenres(data.genres);
            this.createConnections(data.connections);
            
        } catch (error) {
            console.error('Error loading genre data:', error);
        }
    }
    
    createGenres(genresData) {
        genresData.forEach(genreData => {
            // Create genre sphere
            const geometry = new THREE.SphereGeometry(genreData.size / 10, 32, 32);
            const material = new THREE.MeshPhongMaterial({
                color: new THREE.Color(genreData.color),
                emissive: new THREE.Color(genreData.color),
                emissiveIntensity: 0.3,
                transparent: true,
                opacity: 0.8
            });
            
            const sphere = new THREE.Mesh(geometry, material);
            sphere.position.set(
                genreData.position.x,
                genreData.position.y,
                genreData.position.z
            );
            
            // Add glow effect
            const glowGeometry = new THREE.SphereGeometry(genreData.size / 10 + 2, 32, 32);
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: new THREE.Color(genreData.color),
                transparent: true,
                opacity: 0.2
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            sphere.add(glow);
            
            // Add label
            const label = this.createLabel(genreData.name, genreData.size);
            label.position.set(0, genreData.size / 10 + 5, 0);
            sphere.add(label);
            
            // Store genre data
            sphere.userData = genreData;
            this.genres.set(genreData.id, sphere);
            
            // Add to scene
            this.scene.add(sphere);
            
            // Add particles around major genres
            if (genreData.play_count > 100) {
                this.addGenreParticles(sphere, genreData);
            }
        });
    }
    
    createLabel(text, size) {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = 256;
        canvas.height = 64;
        
        context.fillStyle = 'rgba(0, 0, 0, 0)';
        context.fillRect(0, 0, canvas.width, canvas.height);
        
        context.font = `${Math.max(16, size / 2)}px Arial`;
        context.fillStyle = 'white';
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(text, canvas.width / 2, canvas.height / 2);
        
        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
        const sprite = new THREE.Sprite(material);
        sprite.scale.set(size / 2, size / 8, 1);
        
        return sprite;
    }
    
    addGenreParticles(genreSphere, genreData) {
        const particleCount = Math.min(genreData.play_count / 10, 100);
        const geometry = new THREE.BufferGeometry();
        const positions = [];
        const colors = [];
        
        const color = new THREE.Color(genreData.color);
        
        for (let i = 0; i < particleCount; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            const radius = genreData.size / 10 + Math.random() * 10;
            
            positions.push(
                radius * Math.sin(phi) * Math.cos(theta),
                radius * Math.sin(phi) * Math.sin(theta),
                radius * Math.cos(phi)
            );
            
            colors.push(color.r, color.g, color.b);
        }
        
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        
        const material = new THREE.PointsMaterial({
            size: 1,
            vertexColors: true,
            transparent: true,
            opacity: 0.6,
            blending: THREE.AdditiveBlending
        });
        
        const particles = new THREE.Points(geometry, material);
        genreSphere.add(particles);
    }
    
    createConnections(connectionsData) {
        connectionsData.forEach(connection => {
            const sourceGenre = this.genres.get(connection.source);
            const targetGenre = this.genres.get(connection.target);
            
            if (sourceGenre && targetGenre) {
                const material = new THREE.LineBasicMaterial({
                    color: 0x1db954,
                    transparent: true,
                    opacity: connection.strength * 0.5,
                    linewidth: connection.strength * 2
                });
                
                const geometry = new THREE.BufferGeometry().setFromPoints([
                    sourceGenre.position,
                    targetGenre.position
                ]);
                
                const line = new THREE.Line(geometry, material);
                this.connections.push(line);
                this.scene.add(line);
            }
        });
    }
    
    setupEventListeners() {
        // Window resize
        window.addEventListener('resize', () => this.onWindowResize(), false);
        
        // Mouse events
        this.renderer.domElement.addEventListener('mousemove', (e) => this.onMouseMove(e), false);
        this.renderer.domElement.addEventListener('click', (e) => this.onMouseClick(e), false);
    }
    
    onWindowResize() {
        this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    }
    
    onMouseMove(event) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        
        // Update raycaster
        this.raycaster.setFromCamera(this.mouse, this.camera);
        
        // Check for intersections
        const intersects = this.raycaster.intersectObjects(Array.from(this.genres.values()));
        
        // Reset all genres
        this.genres.forEach(genre => {
            genre.material.emissiveIntensity = 0.3;
        });
        
        // Highlight hovered genre
        if (intersects.length > 0) {
            const hoveredGenre = intersects[0].object;
            hoveredGenre.material.emissiveIntensity = 0.8;
            this.container.style.cursor = 'pointer';
        } else {
            this.container.style.cursor = 'default';
        }
    }
    
    onMouseClick(event) {
        // Update raycaster
        this.raycaster.setFromCamera(this.mouse, this.camera);
        
        // Check for intersections
        const intersects = this.raycaster.intersectObjects(Array.from(this.genres.values()));
        
        if (intersects.length > 0) {
            const clickedGenre = intersects[0].object;
            this.selectGenre(clickedGenre);
        }
    }
    
    selectGenre(genreMesh) {
        this.selectedGenre = genreMesh;
        const genreData = genreMesh.userData;
        
        // Animate camera to focus on genre
        const targetPosition = new THREE.Vector3(
            genreData.position.x,
            genreData.position.y,
            genreData.position.z + 50
        );
        
        // Smooth camera animation
        const duration = 1000;
        const startPosition = this.camera.position.clone();
        const startTime = Date.now();
        
        const animateCamera = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const easeProgress = this.easeInOutCubic(progress);
            
            this.camera.position.lerpVectors(startPosition, targetPosition, easeProgress);
            this.camera.lookAt(genreMesh.position);
            
            if (progress < 1) {
                requestAnimationFrame(animateCamera);
            } else {
                // Show genre details
                this.showGenreDetails(genreData);
            }
        };
        
        animateCamera();
    }
    
    showGenreDetails(genreData) {
        // Emit event with genre details
        const event = new CustomEvent('genreSelected', { detail: genreData });
        this.container.dispatchEvent(event);
    }
    
    easeInOutCubic(t) {
        return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        
        // Update controls
        this.controls.update();
        
        // Rotate particles
        this.genres.forEach(genre => {
            genre.children.forEach(child => {
                if (child instanceof THREE.Points) {
                    child.rotation.y += 0.001;
                }
            });
        });
        
        // Render scene
        this.renderer.render(this.scene, this.camera);
    }
    
    async loadJourney(startDate, endDate) {
        try {
            const params = new URLSearchParams();
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);
            
            const response = await fetch(`/api/visualizations/genre-journey?${params}`);
            const data = await response.json();
            
            this.animateJourney(data.journey);
            
        } catch (error) {
            console.error('Error loading journey data:', error);
        }
    }
    
    animateJourney(journeyData) {
        // Create journey path
        const material = new THREE.LineBasicMaterial({
            color: 0x1db954,
            linewidth: 3,
            transparent: true,
            opacity: 0.8
        });
        
        let currentIndex = 0;
        
        const animateStep = () => {
            if (currentIndex >= journeyData.length) return;
            
            const step = journeyData[currentIndex];
            const fromGenre = this.genres.get(step.from_genre);
            const toGenre = this.genres.get(step.to_genre);
            
            if (fromGenre && toGenre) {
                // Create animated path
                const curve = new THREE.CatmullRomCurve3([
                    fromGenre.position,
                    new THREE.Vector3(
                        (fromGenre.position.x + toGenre.position.x) / 2,
                        (fromGenre.position.y + toGenre.position.y) / 2 + 20,
                        (fromGenre.position.z + toGenre.position.z) / 2
                    ),
                    toGenre.position
                ]);
                
                const points = curve.getPoints(50);
                const geometry = new THREE.BufferGeometry().setFromPoints(points);
                const line = new THREE.Line(geometry, material);
                
                this.scene.add(line);
                
                // Animate line drawing
                const drawDuration = 1000;
                const startTime = Date.now();
                
                const animateDraw = () => {
                    const elapsed = Date.now() - startTime;
                    const progress = Math.min(elapsed / drawDuration, 1);
                    
                    // Update line visibility based on progress
                    const visiblePoints = Math.floor(points.length * progress);
                    geometry.setDrawRange(0, visiblePoints);
                    
                    if (progress < 1) {
                        requestAnimationFrame(animateDraw);
                    } else {
                        currentIndex++;
                        setTimeout(animateStep, 500);
                    }
                };
                
                animateDraw();
            } else {
                currentIndex++;
                animateStep();
            }
        };
        
        animateStep();
    }
}

// Export for use
window.GenreGalaxy = GenreGalaxy;