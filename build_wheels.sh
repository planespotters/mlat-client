#!/bin/bash
# Build script for creating Python wheels for multiple architectures

set -e

# Configuration
PACKAGE_NAME="MlatClient"
SUPPORTED_ARCHS=("x86_64" "aarch64" "armv7l")
OUTPUT_DIR="dist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [[ ! -f "setup.py" ]]; then
    log_error "setup.py not found. Please run from the project root directory."
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to build wheels using cibuildwheel
build_with_cibuildwheel() {
    log_info "Building wheels using cibuildwheel..."
    
    # Set cibuildwheel environment variables
    export CIBW_BUILD="cp39-* cp310-* cp311-* cp312-*"
    export CIBW_SKIP="*-win32 *-win_amd64 *-macosx*"
    export CIBW_ARCHS_LINUX="x86_64 aarch64 armv7l"
    
    # Architecture-specific optimizations
    export CIBW_ENVIRONMENT_LINUX="TARGET_ARCH={platform.machine()}"
    
    # Before build commands
    export CIBW_BEFORE_BUILD="pip install --upgrade pip setuptools wheel"
    
    # Test commands
    export CIBW_TEST_COMMAND="python -c 'import _modes; print(\"Module loaded successfully\")'"
    
    if command -v cibuildwheel &> /dev/null; then
        cibuildwheel --output-dir "$OUTPUT_DIR"
        log_success "Wheels built using cibuildwheel"
    else
        log_error "cibuildwheel not found. Install with: pip install cibuildwheel"
        return 1
    fi
}

# Function to build wheel for current architecture
build_native_wheel() {
    local arch=$(uname -m)
    log_info "Building native wheel for architecture: $arch"
    
    # Set optimization flags
    export OPTIMIZE_NATIVE=1
    
    # Clean previous builds
    rm -rf build/ *.egg-info/
    
    # Build wheel
    python3 setup.py bdist_wheel
    
    # Move wheel to output directory
    mv dist/*.whl "$OUTPUT_DIR/"
    
    log_success "Native wheel built for $arch"
}

# Function to build cross-compiled wheels using Docker
build_cross_compiled_wheels() {
    log_info "Building cross-compiled wheels using Docker..."
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker for cross-compilation."
        return 1
    fi
    
    # Build Docker image if it doesn't exist
    if ! docker image inspect mlat-builder:latest &> /dev/null; then
        log_info "Building Docker builder image..."
        docker build -f Dockerfile.multiarch -t mlat-builder:latest .
    fi
    
    for arch in "${SUPPORTED_ARCHS[@]}"; do
        log_info "Building wheel for $arch using Docker..."
        
        # Map architecture names for Docker platform
        case "$arch" in
            "x86_64")
                platform="linux/amd64"
                ;;
            "aarch64")
                platform="linux/arm64"
                ;;
            "armv7l")
                platform="linux/arm/v7"
                ;;
            *)
                log_warning "Unknown architecture: $arch, skipping"
                continue
                ;;
        esac
        
        # Build wheel in container
        docker run --rm --platform="$platform" \
            -v "$(pwd):/src" \
            -v "$(pwd)/$OUTPUT_DIR:/output" \
            -e TARGET_ARCH="$arch" \
            mlat-builder:latest \
            bash -c "
                cd /src && \
                python3 setup.py clean --all && \
                python3 setup.py bdist_wheel && \
                cp dist/*.whl /output/
            "
        
        log_success "Wheel built for $arch"
    done
}

# Function to create source distribution
build_sdist() {
    log_info "Building source distribution..."
    
    # Clean previous builds
    rm -rf build/ *.egg-info/
    
    # Build source distribution
    python3 setup.py sdist
    
    # Move to output directory
    mv dist/*.tar.gz "$OUTPUT_DIR/"
    
    log_success "Source distribution created"
}

# Function to optimize wheels
optimize_wheels() {
    log_info "Optimizing wheels..."
    
    for wheel in "$OUTPUT_DIR"/*.whl; do
        if [[ -f "$wheel" ]]; then
            log_info "Optimizing $(basename "$wheel")"
            
            # Extract wheel
            temp_dir=$(mktemp -d)
            cd "$temp_dir"
            unzip -q "$wheel"
            
            # Strip debug symbols from .so files
            find . -name "*.so" -exec strip --strip-debug {} \; 2>/dev/null || true
            
            # Repack wheel
            zip -r -q "$(basename "$wheel")" .
            mv "$(basename "$wheel")" "$wheel"
            
            # Cleanup
            cd - > /dev/null
            rm -rf "$temp_dir"
        fi
    done
    
    log_success "Wheels optimized"
}

# Main build process
main() {
    log_info "Starting build process for $PACKAGE_NAME"
    
    # Parse command line arguments
    NATIVE_ONLY=false
    USE_DOCKER=false
    USE_CIBUILDWHEEL=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --native-only)
                NATIVE_ONLY=true
                shift
                ;;
            --docker)
                USE_DOCKER=true
                shift
                ;;
            --cibuildwheel)
                USE_CIBUILDWHEEL=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --native-only     Build only for current architecture"
                echo "  --docker          Use Docker for cross-compilation"
                echo "  --cibuildwheel    Use cibuildwheel for building"
                echo "  --help, -h        Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Clean output directory
    rm -rf "$OUTPUT_DIR"/*.whl "$OUTPUT_DIR"/*.tar.gz
    
    # Build wheels based on selected method
    if $USE_CIBUILDWHEEL; then
        build_with_cibuildwheel
    elif $USE_DOCKER; then
        build_cross_compiled_wheels
    elif $NATIVE_ONLY; then
        build_native_wheel
    else
        # Default: try cibuildwheel first, fallback to native
        if command -v cibuildwheel &> /dev/null; then
            build_with_cibuildwheel
        else
            log_warning "cibuildwheel not found, building native wheel only"
            build_native_wheel
        fi
    fi
    
    # Always build source distribution
    build_sdist
    
    # Optimize wheels
    optimize_wheels
    
    # Display results
    log_info "Build complete! Output files:"
    ls -la "$OUTPUT_DIR"
    
    log_success "All builds completed successfully!"
}

# Run main function
main "$@"