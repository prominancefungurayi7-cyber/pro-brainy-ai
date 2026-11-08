(() => {
    const form = document.getElementById('ppt-download-form');
    const status = document.getElementById('ppt-download-status');
    const errorBox = document.getElementById('ppt-download-error');
    if (!form || !status || !errorBox) return;
    const button = form.querySelector('button[type="submit"]');
    let busy = false;

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (busy || !form.reportValidity()) return;
        busy = true;
        button.disabled = true;
        status.hidden = false;
        errorBox.hidden = true;
        status.textContent = 'Creating slides and checking diagrams. This can take a minute.';
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
                cache: 'no-store',
            });
            if (response.redirected && new URL(response.url).pathname === '/login') {
                window.location.assign(response.url);
                return;
            }
            if (!response.ok) {
                const payload = response.headers.get('Content-Type')?.includes('application/json')
                    ? await response.json() : {};
                throw new Error(payload.error || 'The presentation could not be completed. Please try again.');
            }
            if (!response.headers.get('Content-Type')?.includes('presentationml.presentation')) {
                throw new Error('The presentation response was incomplete. Please try again.');
            }
            const blob = await response.blob();
            if (!blob.size) throw new Error('The PowerPoint file was empty. Please try again.');
            const disposition = response.headers.get('Content-Disposition') || '';
            const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || 'presentation.pptx';
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 60000);
            status.textContent = 'PowerPoint created. Your download is starting.';
        } catch (error) {
            errorBox.textContent = error.message || 'The presentation could not be completed.';
            errorBox.hidden = false;
            status.hidden = true;
        } finally {
            busy = false;
            button.disabled = false;
        }
    });
})();
