(() => {
    const input = document.getElementById('id_avatar');
    const preview = document.getElementById('avatar-preview');
    const current = document.getElementById('avatar-current');
    const remove = document.getElementById('id_remove_avatar');
    if (!input || !preview || !current) return;
    let selection = 0;
    const reset = () => {
        preview.hidden = true;
        preview.removeAttribute('src');
        current.hidden = false;
    };
    input.addEventListener('change', () => {
        const version = ++selection;
        reset();
        const file = input.files[0];
        if (!file || file.size > 5 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) return;
        if (remove) remove.checked = false;
        const reader = new FileReader();
        reader.onload = () => {
            if (version !== selection) return;
            preview.src = reader.result;
            preview.hidden = false;
            current.hidden = true;
        };
        reader.readAsDataURL(file);
    });
    remove?.addEventListener('change', () => {
        if (remove.checked) {
            selection++;
            input.value = '';
            reset();
        }
    });
})();
