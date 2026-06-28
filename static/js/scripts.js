document.addEventListener('DOMContentLoaded', function () {
    const planButtons = document.querySelectorAll('.plan-options button');
    const sizeButtons = document.querySelectorAll('.account-sizes button');

    function updateActiveButton(buttons, clickedButton) {
        buttons.forEach(btn => btn.classList.remove('active'));
        clickedButton.classList.add('active');
    }

    planButtons.forEach(button => {
        button.addEventListener('click', function () {
            updateActiveButton(planButtons, this);
            const planType = this.getAttribute('data-plan-type');
            const accountSize = document.querySelector('.account-sizes button.active').getAttribute('data-account-size');
            window.location.href = `/?plan_type=${planType}&account_size=${accountSize}`;
        });
    });

    sizeButtons.forEach(button => {
        button.addEventListener('click', function () {
            updateActiveButton(sizeButtons, this);
            const accountSize = this.getAttribute('data-account-size');
            const planType = document.querySelector('.plan-options button.active').getAttribute('data-plan-type');
            window.location.href = `/?plan_type=${planType}&account_size=${accountSize}`;
        });
    });
});