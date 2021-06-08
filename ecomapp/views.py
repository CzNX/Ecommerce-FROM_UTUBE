import requests
from django.core import paginator
from django.http import request
from django.http.response import JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import ListView,CreateView,View,FormView,TemplateView,DetailView
from . models import *
from .forms import *
from django.urls import reverse_lazy,reverse
from django.db.models import Q
from django.core.paginator import Paginator
from .utils import password_reset_token
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, get_user, login, logout
# freate your views here.


class EcomMixin(object):
    def dispatch(self, request, *args, **kwargs):
        cart_id = self.request.session.get("cart_id", None)
        if cart_id:
            cart_obj = Cart.objects.get(id=cart_id)                      #obj=single one
            if request.user.is_authenticated and request.user.customer:
                cart_obj.customer = request.user.customer
                cart_obj.save()

        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(object):
       def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and Admin.objects.filter(user=request.user).exists():
            pass
        else:
            return redirect("/admin-login")
        return super().dispatch(request, *args, **kwargs)


class HomeView(EcomMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['myname'] = "XYZ"
        all_products = Product.objects.all().order_by("-id")
        paginator = Paginator(all_products, 4)
        page_number = self.request.GET.get('page')
        print(page_number)
        product_list = paginator.get_page(page_number)
        context['product_list'] = product_list
        return context
    


class AllProductsView(EcomMixin,TemplateView):
    template_name = 'allproducts.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["allcategories"] =Category.objects.all()
        return context
    


# class ProductDetailView(DetailView):
#     model = Product
#     context_object_name = 'ran' #def=object
#     template_name = 'productdetail.html'

class ProductDetailView(EcomMixin,TemplateView):
    template_name = "productdetail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        url_slug = self.kwargs['slug']
        product = Product.objects.get(slug=url_slug)
        product.view_count += 1
        product.save()
        context['product'] = product
        return context


class AddToCartView(EcomMixin,TemplateView):
    template_name = "addtocart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # get product id from requested url
        product_id = self.kwargs['pro_id']
        # get product
        product_obj = Product.objects.get(id=product_id)

        # check if cart exists
        cart_id = self.request.session.get("cart_id", None)
        if cart_id:
            cart_obj = Cart.objects.get(id=cart_id)                      #obj=single one
            this_product_in_cart = cart_obj.cartproduct_set.filter(
                product=product_obj)

            # item already exists in cart
            if this_product_in_cart.exists():
                cartproduct = this_product_in_cart.last()
                cartproduct.quantity += 1
                cartproduct.subtotal += product_obj.selling_price
                cartproduct.save()
                cart_obj.total += product_obj.selling_price
                cart_obj.save()
            # new item is added in cart
            else:
                cartproduct = CartProduct.objects.create(
                    cart=cart_obj, product=product_obj, rate=product_obj.selling_price, quantity=1, subtotal=product_obj.selling_price)
                cart_obj.total += product_obj.selling_price
                cart_obj.save()

        else:
            cart_obj = Cart.objects.create(total=0)
            self.request.session['cart_id'] = cart_obj.id
            cartproduct = CartProduct.objects.create(
                cart=cart_obj, product=product_obj, rate=product_obj.selling_price, quantity=1, subtotal=product_obj.selling_price)
            cart_obj.total += product_obj.selling_price
            cart_obj.save()

        return context
    


class MyCartView(EcomMixin,TemplateView):
    template_name = 'mycart.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart_id = self.request.session.get('cart_id',None) 
        
        if cart_id:
            cart = Cart.objects.get(id=cart_id)
        else:
            cart= None
        
        context['cart']=cart

        return context
    

class ManageCartView(EcomMixin,View):
    def get(self,request,*args,**kwargs):
        # print('helllooo')
        cp_d = self.kwargs['cp_id']
        action = request.GET.get('action')
        # print(cp_d,action)
        cp_obj = CartProduct.objects.get(id=cp_d)
        # cp = Product.objects.get(id=cp_d)
        cart_obj = cp_obj.cart

        if action=='inc':
           cp_obj.quantity += 1
           cp_obj.subtotal += cp_obj.rate
           cp_obj.save()
           cart_obj.total += cp_obj.rate
           cart_obj.save()
        
        elif action=='dcr':
            cp_obj.quantity -= 1
            cp_obj.subtotal -= cp_obj.rate
            cp_obj.save()
            cart_obj.total -= cp_obj.rate
            cart_obj.save()
            
            if cp_obj.quantity ==0:
                cp_obj.delete()

        elif action=='rmv':
            cart_obj.total -= cp_obj.subtotal
            cart_obj.save()
            cp_obj.delete()
        else:
            pass 
        return redirect('ecomapp:mycart')



class EmptyCartView(EcomMixin,TemplateView):
    def get(self,request,*args,**kwargs):
        cart_id = request.session.get('cart_id',None)
        if cart_id:
            cart = Cart.objects.get(id=cart_id)
            cart.cartproduct_set.all().delete()
            cart.total = 0
            cart.save()
        return redirect('ecomapp:mycart')    

class CheckoutView(EcomMixin,CreateView):
    template_name = 'checkout.html'
    form_class = CheckoutForm
    success_url = reverse_lazy('ecomapp:home')

    def dispatch(self, request, *args, **kwargs):                  #like __init__ executed before every method
        if request.user.is_authenticated and request.user.customer:
            pass
        else:
            return redirect('/login/?next=/checkout/')
        return super().dispatch(request, *args, **kwargs)
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart_id = self.request.session.get('cart_id',None) 
        
        if cart_id:
            cart_obj = Cart.objects.get(id=cart_id)
        else:
            cart_obj= None
        
        context['cart']=cart_obj

        return context
    def form_valid(self, form):                         #form_valid method is a type of post method available in createview formview and updateview
        cart_id = self.request.session.get("cart_id")
        if cart_id:
            cart_obj = Cart.objects.get(id=cart_id)
            form.instance.cart = cart_obj                                     #To create new Order objec
            form.instance.subtotal = cart_obj.total           #to supply use form_valid() method using form.instance.field_name = value.
            form.instance.discount = 0
            form.instance.total = cart_obj.total
            form.instance.order_status = "Order Received"
            del self.request.session['cart_id']
            pm = form.cleaned_data.get("payment_method")
            order = form.save()
            if pm == "Khalti":
                return redirect(reverse("ecomapp:khaltirequest") + "?o_id=" + str(order.id))
            elif pm == "Esewa":
                return redirect(reverse("ecomapp:esewarequest") + "?o_id=" + str(order.id))
        else:
            return redirect("ecomapp:home")
        return super().form_valid(form)   
    
class KhaltiRequestView(View):
    def get(self,request,*args,**kwargs):
        o_id = request.GET.get('o_id')
        order = Order.objects.get(id=o_id)
        context = {'order':order}
        return render(request,'khaltirequest.html',context)


class KhaltiVerifyView(View):
    def get(self,request,*args,**kwargs):
        token = request.GET.get('token')
        amount = request.GET.get('amount')
        o_id = request.GET.get('order_id')
        print(token,amount,o_id)
        url = "https://khalti.com/api/v2/payment/verify/"
        payload = {
        "token": token,
        "amount": amount
        }
        headers = {
        "Authorization": "Key test_secret_key_e870cfff05194c559c7e89cab66ab904"
        }
        order_obj = Order.objects.get(id=o_id)
        response = requests.post(url, payload, headers = headers)
        
       
        print(response)
        resp_dict = response.json()
        if resp_dict.get('idx'):
            success = True
            order_obj.payment_completed = True
            order_obj.save()
        else:
            success=False    

        data = {
            'success':success
        }
        return JsonResponse(data)


class EsewaRequestView(View):
    def get(self,request,*args,**kwargs):
        o_id = request.GET.get('o_id')
        order = Order.objects.get(id=o_id)
        context = {'order':order}
        return render(request,'esewarequest.html',context)


class EsewaVerifyView(View):
    def get(self, request, *args, **kwargs):
        import xml.etree.ElementTree as ET
        oid = request.GET.get("oid")
        amt = request.GET.get("amt")
        refId = request.GET.get("refId")

        url = "https://uat.esewa.com.np/epay/transrec"
        d = {
            'amt': amt,
            'scd': 'EPAYTEST',
            'rid': refId,
            'pid': oid,
        }
        resp = requests.post(url, d)
        root = ET.fromstring(resp.content)
        # print(root[0].text.strip())
        status = root[0].text.strip()
        # print(status)
        order_id = oid.split("_")[1]
        order_obj = Order.objects.get(id=order_id)
        if status == "Success":
            order_obj.payment_completed = True
            order_obj.save()
            return redirect("/")
        else:
            # return redirect('/')
            return redirect("/esewa-request/?o_id="+order_id)




class CustomerRegistrationView(CreateView):
    template_name = 'customerregistration.html'
    form_class = CustomerRegistrationForm
    success_url = reverse_lazy('ecomapp:home')

    def form_valid(self, form):                                 #to handle /customize form (can use any post method here)
        username = form.cleaned_data.get("username")             #form.cleaned_data.get('fieldname') to get data
        password = form.cleaned_data.get("password")
        email = form.cleaned_data.get("email")
        user = User.objects.create_user(username, email, password)         #create user manually
        form.instance.user = user                                    #supply currently created user to make customer registration
        login(self.request, user)
        return super().form_valid(form)

    def get_success_url(self):
        if "next" in self.request.GET:
            next_url = self.request.GET.get("next")
            return next_url
        else:
            return self.success_url
    



class CustomerLogoutView(View):
    def get(self,request):
        logout(request)
        return redirect('ecomapp:home')

class CustomerLoginView(FormView):
    template_name = 'customerlogin.html'
    form_class = CustomerLoginForm
    success_url = reverse_lazy('ecomapp:home')

    def form_valid(self, form):
        uname = form.cleaned_data.get('username')   
        password = form.cleaned_data.get('password')
        usr = authenticate(username=uname,password=password)                 #if no match None is returned
        if usr is not None and Customer.objects.filter(user=usr).exists():
            login(self.request,usr)
        else:
            return render(self.request,self.template_name,{'form':self.form_class,'error':'Invalid Credentials'})    
        return super().form_valid(form)
    
    def get_success_url(self):
        if "next" in self.request.GET:
            next_url = self.request.GET.get("next")
            return next_url
        else:
            return self.success_url



class CustomerProfileView(TemplateView):
    template_name = "customerprofile.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and Customer.objects.filter(user=request.user).exists():
            pass
        else:
            return redirect("/login/?next=/profile/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.request.user.customer
        # print(customer)
        context['customer'] = customer
        orders = Order.objects.filter(cart__customer=customer).order_by("-id")             # Field Lookups i.e fieldname__lookuptype=value
        context["orders"] = orders                                                   #also =  ( __ ) To Reference Foreign Key Model Class’s Attribute.
        return context                                                                  #user__username = 'tom' eg


class CustomerOrderDetailView(DetailView):
    template_name = 'customerorderdetail.html'
    model = Order
    context_object_name = 'ord_obj'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and Customer.objects.filter(user=request.user).exists():
            order_id = self.kwargs["pk"]
            order = Order.objects.get(id=order_id)
            if request.user.customer != order.cart.customer:
                return redirect("ecomapp:customerprofile")
        else:
            return redirect("/login/?next=/profile/")
        return super().dispatch(request, *args, **kwargs)


class AdminLoginView(FormView):
    template_name = 'adminpages/adminlogin.html'
    form_class=CustomerLoginForm
    success_url = reverse_lazy('ecomapp:adminhome')

    def form_valid(self, form):
        uname = form.cleaned_data.get('username')   
        password = form.cleaned_data.get('password')
        usr = authenticate(username=uname,password=password)                       #if no match None is returned
        if usr is not None and Admin.objects.filter(user=usr).exists():
            login(self.request,usr)
        else:
            return render(self.request,self.template_name,{'form':self.form_class,'error':'Invalid Credentials'})    
        return super().form_valid(form)


class AdminHomeView(AdminRequiredMixin,TemplateView):
    template_name = 'adminpages/adminhome.html'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pendingorders"] =Order.objects.filter(order_status = 'Order Received').order_by('-id')
        return context
    


class AdminOrderDetailView(AdminRequiredMixin,DetailView):
    template_name = 'adminpages/adminorderdetail.html'
    model = Order
    context_object_name='ord_obj'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["allstatus"] =ORDER_STATUS
        return context
    


class AdminOrderListView(AdminRequiredMixin,ListView):
    template_name = 'adminpages/adminorderlist.html'
    queryset =Order.objects.all().order_by('-id')
    context_object_name = 'allorders'


class AdminOrderStatuChangeView(AdminRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        order_id = self.kwargs["pk"]
        order_obj = Order.objects.get(id=order_id)
        new_status = request.POST.get("status")
        # print(new_status)
        order_obj.order_status = new_status
        order_obj.save()
        return redirect(reverse_lazy("ecomapp:adminorderdetail", kwargs={"pk": order_id}))




class SearchView(TemplateView):
    template_name = "search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kw = self.request.GET.get("keyword")
        results = Product.objects.filter(
            Q(title__icontains=kw) | Q(description__icontains=kw) | Q(return_policy__icontains=kw))   
                                                                                                  # Q used to implement or logic in search mechanism
        print(results)
        context["results"] = results
        return context







class PasswordForgotView(FormView):
    template_name = "forgotpassword.html"
    form_class = PasswordForgotForm
    success_url = "/forgot-password/?m=s"

    def form_valid(self, form):
        # get email from user
        email = form.cleaned_data.get("email")
        # get current host ip/domain
        url = self.request.META['HTTP_HOST']                                              # 127.0.0.1:8000/
        # get customer and then user
        customer = Customer.objects.get(user__email=email)
        user = customer.user
        # send mail to the user with email
        text_content = 'Please Click the link below to reset your password. '
        html_content = url + "/password-reset/" + email + \
            "/" + password_reset_token.make_token(user) + "/"
        send_mail(
            'Password Reset Link | Django Ecommerce',
            text_content + html_content,                                              #token=anxegi-bc37df1e0629e5715d365b4asdsadasd/
            settings.EMAIL_HOST_USER,                                      #sender 
            [email,'ryukxtha12@gmail.com'],                                    #receivers
            fail_silently=False,
        )
        return super().form_valid(form)

class PasswordResetView(FormView):
    template_name = "passwordreset.html"
    form_class = PasswordResetForm
    success_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        email = self.kwargs.get("email")
        user = User.objects.get(email=email)
        token = self.kwargs.get("token")
        if user is not None and password_reset_token.check_token(user, token):
            pass
        else:
            return redirect(reverse("ecomapp:passworforgot") + "?m=e")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        password = form.cleaned_data['new_password']
        email = self.kwargs.get("email")
        user = User.objects.get(email=email)
        user.set_password(password)                                      #set_password is a User object method
        user.save()
        return super().form_valid(form)


class AboutView(EcomMixin,TemplateView):
    template_name = 'about.html'




class ContactView(EcomMixin,TemplateView):
    template_name = 'contact.html'


class AdminProductListView(AdminRequiredMixin, ListView):
    template_name = "adminpages/adminproductlist.html"
    queryset = Product.objects.all().order_by("-id")
    context_object_name = "allproducts"


class AdminProductCreateView(AdminRequiredMixin, CreateView):
    template_name = "adminpages/adminproductcreate.html"
    form_class = ProductForm
    success_url = reverse_lazy("ecomapp:adminproductlist")

    def form_valid(self, form):
        p = form.save()                                                              #just created form is saved in p
        images = self.request.FILES.getlist("more_images")                       #To retrieve  'more_image'  variable from our Form
        for i in images:
            ProductImage.objects.create(product=p, image=i)
        return super().form_valid(form)
