// A lightweight observer to detect when story chapters scroll into view
document.addEventListener('DOMContentLoaded', () => {
    
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.5 // Trigger when 50% of the element is visible
    };

    const chapterObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Remove active class from all
                document.querySelectorAll('.story-chapter').forEach(el => el.classList.remove('active'));
                
                // Add active class to current
                entry.target.classList.add('active');

                // Send the chapter ID back to the Python Shiny Backend
                const chapterId = entry.target.getAttribute('data-chapter');
                if (Shiny && Shiny.setInputValue) {
                    Shiny.setInputValue('scroll_chapter', chapterId);
                }
            }
        });
    }, observerOptions);

    // Initial query but allow a slight delay for Shiny UI to fully render
    setTimeout(() => {
        const chapters = document.querySelectorAll('.story-chapter');
        chapters.forEach(chapter => chapterObserver.observe(chapter));
    }, 1000);
});