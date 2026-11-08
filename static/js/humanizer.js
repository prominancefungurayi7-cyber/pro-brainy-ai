(() => {
    const form = document.getElementById('humanizer-form');
    const fileInput = document.getElementById('file');
    const panel = document.getElementById('humanizer-progress');
    const progress = document.getElementById('humanizer-progress-bar');
    const percent = document.getElementById('humanizer-percent');
    const status = document.getElementById('humanizer-progress-status');
    const submit = document.getElementById('humanizer-submit');
    if (!form || !fileInput || !panel || !progress || !percent || !status || !submit) return;

    function showProgress(value, message) {
        const safeValue = Math.max(0, Math.min(100, Number(value) || 0));
        progress.value = safeValue;
        percent.textContent = `${safeValue}%`;
        status.textContent = message;
    }

    form.addEventListener('submit', async (event) => {
        const file = fileInput.files?.[0];
        if (!file || !file.name.toLowerCase().endsWith('.docx')) return;
        event.preventDefault();
        panel.hidden = false;
        panel.classList.remove('is-error');
        showProgress(0, 'Preparing your Word document.');
        submit.disabled = true;
        const originalLabel = submit.textContent;
        submit.textContent = 'Humanizing document…';

        const chunks = [];
        let filename = 'humanized.docx';
        let expectedSize = null;
        let expectedHash = null;
        let receivedSize = 0;
        let completed = false;
        let preservedCount = 0;
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { Accept: 'text/event-stream' },
                credentials: 'same-origin',
                cache: 'no-store',
            });
            if (response.redirected && new URL(response.url).pathname === '/login') {
                window.location.assign(response.url);
                return;
            }
            if (response.status === 413) throw new Error('This Word file is too large to upload.');
            if (!response.ok || !response.headers.get('Content-Type')?.includes('text/event-stream') || !response.body) {
                throw new Error('The document request failed. Please try again.');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            const processFrame = async (frame) => {
                const data = frame.split(/\r\n|\n|\r/).find((line) => line.startsWith('data: '));
                if (!data) return;
                const update = JSON.parse(data.slice(6));
                if (update.type === 'progress') {
                    preservedCount = update.preserved || preservedCount;
                    const detail = update.total
                        ? `${update.processed} of ${update.total} body paragraphs rewritten.` +
                          (update.preserved
                              ? ` ${update.preserved} complex paragraphs are preserved unchanged.`
                              : '')
                        : 'Reading your Word document.';
                    showProgress(update.percent, detail);
                } else if (update.type === 'file-start') {
                    filename = update.filename || filename;
                    expectedSize = Number(update.size);
                    expectedHash = update.sha256;
                    if (!Number.isSafeInteger(expectedSize) || expectedSize <= 0 ||
                        !/^[a-f0-9]{64}$/i.test(expectedHash || '')) {
                        throw new Error('The document response was incomplete. Please try again.');
                    }
                    showProgress(95, 'Preparing the completed Word file.');
                } else if (update.type === 'file-chunk') {
                    if (expectedSize === null) throw new Error('The document arrived out of order. Please try again.');
                    const binary = atob(update.data);
                    const bytes = new Uint8Array(binary.length);
                    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
                    receivedSize += bytes.length;
                    if (receivedSize > expectedSize) throw new Error('The document was damaged during transfer. Please try again.');
                    chunks.push(bytes);
                } else if (update.type === 'error') {
                    throw new Error(update.message || 'The document could not be completed.');
                } else if (update.type === 'complete') {
                    if (expectedSize === null || receivedSize !== expectedSize || !chunks.length) {
                        throw new Error('The document was incomplete. Please try again.');
                    }
                    const blob = new Blob(chunks, {
                        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    });
                    if (globalThis.crypto?.subtle) {
                        const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
                        const actualHash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
                        if (actualHash !== expectedHash.toLowerCase()) {
                            throw new Error('The document was damaged during transfer. Please try again.');
                        }
                    }
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = filename;
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                    setTimeout(() => URL.revokeObjectURL(url), 60000);
                    completed = true;
                    showProgress(100, 'Complete. Your Word file is downloading.' +
                        (preservedCount ? ` ${preservedCount} complex paragraphs stayed unchanged.` : ''));
                }
            };
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                let boundary;
                while ((boundary = /\r\n\r\n|\n\n|\r\r/.exec(buffer)) !== null) {
                    const frame = buffer.slice(0, boundary.index);
                    buffer = buffer.slice(boundary.index + boundary[0].length);
                    await processFrame(frame);
                }
            }
            buffer += decoder.decode();
            if (buffer.trim()) await processFrame(buffer);
            if (!completed) throw new Error('The document connection ended before the file was complete.');
        } catch (error) {
            panel.classList.add('is-error');
            status.textContent = error.message || 'The document could not be completed. Please try again.';
        } finally {
            submit.disabled = false;
            submit.textContent = originalLabel;
        }
    });
})();
