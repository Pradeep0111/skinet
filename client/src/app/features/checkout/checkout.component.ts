import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { OrderSummaryComponent } from "../../shared/components/order-summary/order-summary.component";
import { MatStepper, MatStep, MatStepperNext, MatStepperPrevious } from "@angular/material/stepper";
import { Router, RouterLink } from "@angular/router";
import { MatAnchor, MatButton } from "@angular/material/button";
import { StripeService } from '../../Core/services/stripe.service';
import { ConfirmationToken, StripeAddressElement, StripeAddressElementChangeEvent, StripePaymentElement, StripePaymentElementChangeEvent } from "@stripe/stripe-js";
import { SnackbarService } from '../../Core/services/snackbar.service';
import { MatCheckbox, MatCheckboxChange } from "@angular/material/checkbox";
import { StepperSelectionEvent } from '@angular/cdk/stepper';
import { Address } from '../../shared/models/user';
import { AccountService } from '../../Core/services/account.service';
import { firstValueFrom } from 'rxjs';
import { CheckoutDeliveryComponent } from "./checkout-delivery/checkout-delivery.component";
import { CheckoutReviewComponent } from "./checkout-review/checkout-review.component";
import { CartService } from '../../Core/services/cart.service';
import { CurrencyPipe } from "@angular/common";
import { MatProgressSpinner } from "@angular/material/progress-spinner";
import { OrderToCreate, ShippingAddress } from '../../shared/models/order';
import { OrderService } from '../../Core/services/order.service';

@Component({
  selector: 'app-checkout',
  imports: [OrderSummaryComponent, MatStepper, MatStep, RouterLink, MatAnchor, MatStepperNext, MatCheckbox, CheckoutDeliveryComponent, MatButton, MatStepperPrevious, CheckoutReviewComponent, CurrencyPipe, MatProgressSpinner],
  templateUrl: './checkout.component.html',
  styleUrl: './checkout.component.scss',
})
export class CheckoutComponent implements OnInit, OnDestroy{
  private stripeService = inject(StripeService);
  private accountService = inject(AccountService);
  cartService = inject(CartService);
  private orderService = inject(OrderService);
  private snackBar = inject(SnackbarService)
  private router = inject(Router);
  addressElement? : StripeAddressElement;
  paymentElement? : StripePaymentElement;
  saveAddress = false;
  completionStatus = signal<{address : boolean,  delivery: boolean, card : boolean,}>(
    {address : false, delivery: false, card :  false}
  )
  confirmationToken?: ConfirmationToken;
  loading = false;
  
  async ngOnInit() {
    try {
      this.addressElement = await this.stripeService.createAddressElement();
      this.addressElement.mount('#address-element');
      this.addressElement.on('change', this.handleAddressChange)
      
      this.paymentElement = await this.stripeService.createPaymentElement();
      this.paymentElement.mount('#payment-element');
      this.paymentElement.on('change', this.handlePaymentChange);
    } catch (error: any) {
      this.snackBar.error(error.message);
    }
  }
  handlePaymentChange = (event: StripePaymentElementChangeEvent) => {
    this.completionStatus.update(state => {
      state.card = event.complete;
      return state;
    })
  }
  
  handleAddressChange = (event : StripeAddressElementChangeEvent) =>{
    this.completionStatus.update(status => {
      status.address = event.complete;
      return status;
    })
  }
  
  handleDeliveryChange(event: boolean) {
    this.completionStatus.update(state => {
      state.delivery = event;
      return state;
    })
  }

  async getConfirmationToken() {
    try {
      if(Object.values(this.completionStatus()).every(status => status === true)){
        const result = await this.stripeService.createConfirmationToken();
        if(result.error) throw new Error(result.error.message);
        this.confirmationToken = result.confirmationToken;
        console.log(this.confirmationToken);
      }
    } catch (error : any) {
      this.snackBar.error(error.message);
    }
  }

  async onStepChange(event: StepperSelectionEvent){
    if(event.selectedIndex === 1){
      if(this.saveAddress){
        const address = await this.getAddressFromStripeAddress() as Address;
        address && firstValueFrom(this.accountService.updateAddress(address));
      }
    }
    if(event.selectedIndex === 2){
      await firstValueFrom(this.stripeService.createOrUpdatePaymentIntent())
    }
    if(event.selectedIndex === 3){
      await this.getConfirmationToken();
    }
  }

  async confirmPayment(stepper: MatStepper){
    this.loading = true;
    try {
      if(this.confirmationToken){
        const result = await this.stripeService.confirmPayment(this.confirmationToken);
        
        if(result.paymentIntent?.status === 'succeeded'){
          const order = await this.createOrderModel();
          const orderResult = await firstValueFrom(this.orderService.createOrder(order));
          if(orderResult){
            this.orderService.orderComplete = true;
            this.cartService.deleteCart();
            this.cartService.selectedDelivery.set(null);
            this.router.navigateByUrl('/checkout/success');
          } else{
            throw new Error('Order creation faile');
          }
        } else if(result.error){
          throw new Error(result.error.message);
        } else{
          throw new Error('Something went wrong');
        }
      }
    } catch (error :any) {
      this.snackBar.error(error.message || 'Something went wrong!');
    } finally{
      this.loading = false;
    }
  }

  private async createOrderModel() : Promise<OrderToCreate>{
    const cart = this.cartService.cart();
    const shippingAddress = await this.getAddressFromStripeAddress() as ShippingAddress
    const card = this.confirmationToken?.payment_method_preview.card;

    if(!cart?.id || !cart?.deliveryMethodId || !shippingAddress || !card){
      throw new Error('Missing required information to create order');
    }
    return {
      cartId : cart.id,
      deliveryMethodId : cart.deliveryMethodId,
      shippingAddress : shippingAddress,
      paymentSummary : {
        last4 : +card.last4,
        brand : card.brand,
        expMonth : card.exp_month,
        expYear : card.exp_year
      },
      discount : this.cartService.totals()?.discount
    }
  }
  
  private async getAddressFromStripeAddress(): Promise<Address | ShippingAddress | null>{
    const result = await this.addressElement?.getValue();
    const address = result?.value.address;
    if(address){
      return{
        name : result.value.name,
        line1 : address.line1,
        line2 : address.line2 || undefined,
        city : address.city,
        state : address.state,
        country : address.country,
        postalCode : address.postal_code
      }
    }
    else return null;
  }

  onSaveAddressCheckboxChange(event: MatCheckboxChange) {
    this.saveAddress = event.checked;
  }
  
  ngOnDestroy() {
    this.stripeService.disposeElements();
  }
}
