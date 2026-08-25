import base64
import io
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask


def generate_wifi_qr_code(
    ssid: str,
    password: str,
    auth_type: str = "WPA",
    hidden: bool = False
) -> str:
    """
    Genera un QR Code formattato secondo lo standard Wi-Fi universale:
    WIFI:S:<SSID>;T:<AUTH_TYPE>;P:<PASSWORD>;H:<HIDDEN>;;
    Ritorna una stringa data URL in formato PNG Base64 (data:image/png;base64,...).
    """
    # Escaping dei caratteri speciali standard Wi-Fi
    escaped_ssid = ssid.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:")
    escaped_pass = password.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:")
    
    hidden_flag = "true" if hidden else "false"
    wifi_string = f"WIFI:S:{escaped_ssid};T:{auth_type};P:{escaped_pass};H:{hidden_flag};;"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(wifi_string)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        color_mask=SolidFillColorMask(back_color=(15, 23, 42), front_color=(56, 189, 248))  # Dark slate background + Sky blue foreground
    )

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_img = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_img}"
