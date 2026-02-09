// /static/hero.js

const heroCards = [
    { title: "Технологии", sub: "Сближают ли нас технологии или наоборот отдаляют?" },
    { title: "Путешествия", sub: "Какое место ты бы хотел посетить следующим?" },
    { title: "Карьера", sub: "Что для тебя важнее - рост или стабильность?" },
    { title: "Продуктивность", sub: "Опиши свой идеальный рабочий день." },
    { title: "Отношения", sub: "Сложнее находить друзей онлайн или офлайн?" },
    { title: "Музыка", sub: "Какой трек крутится у тебя в голове сегодня?" },
    { title: "Фильм", sub: "Какой фильм должен посмотреть каждый?" },
    { title: "Еда", sub: "Ты скорее пробуешь новое или выбираешь проверенное?" },
    { title: "Фитнес", sub: "Что мотивирует тебя двигаться вперёд?" },
    { title: "Будущее", sub: "Какие технологии изменят наш быт через 5 лет?" }
];

(function () {
    function waitForHeroCard(timeout = 10000) {
        return new Promise((resolve, reject) => {
            const start = Date.now();
            const tick = () => {
                const card = document.querySelector(".hero-card");
                if (card) return resolve(card);
                if (Date.now() - start > timeout) return reject(new Error("hero-card not found within timeout"));
                requestAnimationFrame(tick);
            };
            tick();
        });
    }

    function safeText(node, text) {
        if (!node) return;
        node.textContent = text;
    }

    function initRotation(card) {
        const titleEl = card.querySelector(".hero-title");
        const subEl = card.querySelector(".hero-sub");

        if (!titleEl || !subEl) {
            console.warn("hero-card found but missing .hero-title or .hero-sub");
            return;
        }

        let index = 0;
        const fadeMs = 300;

        function updateHeroCard() {
            card.classList.add("fade-out");

            setTimeout(() => {
            const item = heroCards[index];
            safeText(titleEl, item.title);
            safeText(subEl, item.sub);

            card.classList.remove("fade-out");
            index = (index + 1) % heroCards.length;
            }, fadeMs);
        }

        // show initial content immediately
        updateHeroCard();

        // смена каждые 3 секунды
        const intervalId = setInterval(updateHeroCard, 7000);

        // возврат функции для остановки, если нужно
        return () => clearInterval(intervalId);
    }

    // Запуск: дождёмся появления карточки (максимум 10 с)
    document.addEventListener("DOMContentLoaded", () => {
        waitForHeroCard(10000)
            .then(card => initRotation(card))
            .catch(err => {console.error("Не удалось инициализировать hero rotation:", err);});
    });
})();
