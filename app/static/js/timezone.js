document.addEventListener('DOMContentLoaded', function() {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    document.cookie = `timezone=${timezone};path=/`;
});