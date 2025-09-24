"""QR code generation utility."""
import io
import base64
from typing import Optional, Dict
import logging

# Optional dependencies: qrcode and PIL
try:
    import qrcode  # type: ignore
    from qrcode.image.styledpil import StyledPilImage  # type: ignore
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer  # type: ignore
    from PIL import Image, ImageDraw  # type: ignore
    QR_DEPS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    qrcode = None  # type: ignore
    StyledPilImage = None  # type: ignore
    RoundedModuleDrawer = None  # type: ignore
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    QR_DEPS_AVAILABLE = False

logger = logging.getLogger(__name__)

# 1x1 transparent PNG placeholder (base64)
_PLACEHOLDER_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP+7KQn2wAAAABJRU5ErkJggg=="
)
_PLACEHOLDER_PNG_BYTES = base64.b64decode(_PLACEHOLDER_PNG_B64)


class _PlaceholderImage:
    """Minimal stand-in for PIL Image with save() method."""

    def __init__(self, data: bytes):
        self._data = data
        self.size = (1, 1)

    def save(self, fp, format: str = "PNG") -> None:  # noqa: A003 - match PIL API
        fp.write(self._data)


class QRCodeGenerator:
    """Generate QR codes with custom styling."""
    
    def generate_qr_code(
        self,
        data: str,
        size: int = 10,
        logo_url: Optional[str] = None,
        color: str = "#000000",
        background_color: str = "#FFFFFF",
    ) -> "Image":
        """
        Generate a QR code image.
        
        Args:
            data: Data to encode in QR code
            size: Size multiplier (10 = 300x300 pixels)
            logo_url: Optional logo URL to embed
            color: Foreground color (hex or color name)
            background_color: Background color
            
        Returns:
            PIL Image object
        """
        if not QR_DEPS_AVAILABLE:
            logger.warning("QR dependencies not installed; returning placeholder image")
            return _PlaceholderImage(_PLACEHOLDER_PNG_BYTES)  # type: ignore[return-value]
        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H if logo_url else qrcode.constants.ERROR_CORRECT_L,
            box_size=size,
            border=4,
        )
        
        # Add data
        qr.add_data(data)
        qr.make(fit=True)
        
        # Create styled image
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            fill_color=color,
            back_color=background_color,
        )
        
        # Add logo if provided
        if logo_url:
            img = self._add_logo(img, logo_url)
        
        return img
    
    def _add_logo(self, qr_img: "Image", logo_url: str) -> "Image":
        """Add logo to center of QR code.

        Notes:
            - Lazy-imports requests to avoid hard dependency at startup.
            - Applies a circular mask to the logo and pastes it centered.
        """
        if not QR_DEPS_AVAILABLE:
            return qr_img

        try:
            # Lazy import to avoid hard dependency at startup
            import requests  # type: ignore

            # Download logo
            response = requests.get(logo_url, timeout=5)
            response.raise_for_status()
            logo = Image.open(io.BytesIO(response.content)).convert("RGBA")

            # Compute sizes
            # qrcode may return a wrapper with get_image(); handle both
            base_img = qr_img.get_image() if hasattr(qr_img, "get_image") else qr_img
            qr_width, qr_height = base_img.size
            logo_size = max(16, min(qr_width, qr_height) // 10)

            # Resize logo
            resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
            logo = logo.resize((logo_size, logo_size), resample=resampling)

            # Create circular mask same size as logo
            mask = Image.new("L", (logo_size, logo_size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, logo_size, logo_size), fill=255)

            # Paste centered
            pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
            base_img.paste(logo, pos, mask)
        except Exception as e:  # pragma: no cover - best-effort logo addition
            logger.warning("Failed to add logo to QR: %s", e)

        # Return the possibly-modified base image (PIL Image)
        return base_img if 'base_img' in locals() else qr_img

    def generate_qr_code_svg(
        self,
        data: str,
        size: int = 256,
        color: str = "#000000",
        background_color: str = "#FFFFFF",
        logo_url: Optional[str] = None,
    ) -> str:
        """Return a minimal SVG placeholder. Avoids hard deps.

        Note: This is a stub. For production-quality vector QR, integrate
        qrcode's SVG factory and proper rendering.
        """
        # Simple placeholder SVG with encoded text
        safe_text = (data[:64] + "…") if len(data) > 64 else data
        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 {size} {size}'>"
            f"<rect width='100%' height='100%' fill='{background_color}'/>"
            f"<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' fill='{color}'"
            f" font-family='monospace' font-size='{int(size*0.08)}'>QR PLACEHOLDER</text>"
            f"<title>{safe_text}</title>"
            f"</svg>"
        )

    def generate_qr_code_pdf(
        self,
        data: str,
        size: int = 256,
        color: str = "#000000",
        background_color: str = "#FFFFFF",
        logo_url: Optional[str] = None,
    ) -> bytes:
        """Return PNG bytes as a simple placeholder for PDF output.

        This avoids adding a heavy PDF dependency. Consumers can still download
        a file. Replace with a true PDF generator later.
        """
        img = self.generate_qr_code(data=data, size=max(10, size // 25), logo_url=logo_url, color=color, background_color=background_color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    
    def generate_batch_qr_codes(
        self,
        tables: list,
        business_slug: str,
        **kwargs
    ) -> Dict[str, "Image"]:
        """
        Generate QR codes for multiple tables.
        
        Args:
            tables: List of table objects
            business_slug: Business URL slug
            **kwargs: Additional arguments for generate_qr_code
            
        Returns:
            Dictionary mapping table numbers to QR images
        """
        qr_codes = {}
        
        for table in tables:
            chat_url = f"https://x-sevenai.com/chat?business={business_slug}&table={table.qr_code_id}"
            qr_img = self.generate_qr_code(chat_url, **kwargs)
            qr_codes[table.table_number] = qr_img
        
        return qr_codes