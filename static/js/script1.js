const SignInBtnLink=document.querySelector('.signInBtn-link');
const SignUpBtnLink=document.querySelector('.signUpBtn-link');
const wrapper=document.querySelector('.wrapper');
SignUpBtnLink.addEventListener('click',() =>{
    wrapper.classList.toggle('active');
});
SignInBtnLink.addEventListener('click',() =>{
    wrapper.classList.toggle('active');
});
