(() => {
    const forms = document.querySelectorAll('.tool-container > form:not(#humanizer-form):not(#ppt-download-form)');
    forms.forEach((form) => {
        const submit = form.querySelector('button[type="submit"]');
        if (!submit) return;
        const label = submit.textContent;
        const status = document.createElement('p');
        status.className = 'tool-submit-status';
        status.setAttribute('role', 'status');
        status.setAttribute('aria-live', 'polite');
        status.hidden = true;
        submit.insertAdjacentElement('afterend', status);
        let busy = false;

        form.addEventListener('submit', (event) => {
            if (busy) {
                event.preventDefault();
                return;
            }
            if (!form.checkValidity()) return;
            busy = true;
            submit.disabled = true;
            submit.textContent = 'Working…';
            status.textContent = 'Your request is being processed. This can take a moment.';
            status.hidden = false;
        });

        window.addEventListener('pageshow', () => {
            busy = false;
            submit.disabled = false;
            submit.textContent = label;
            status.hidden = true;
        });
    });
})();
