from django.core.exceptions import ValidationError

def validate_video_size(file):
    if file.size > 100 * 1024 * 1024:
        raise ValidationError('Maximum video size is 100 MB.')
def validate_image_size(file):
    if file.size > 10 * 1024 * 1024:
        raise ValidationError('Maximum image size is 10 MB.')
