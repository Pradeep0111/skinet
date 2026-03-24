import { Component, inject } from '@angular/core';
import { RouterLink } from "@angular/router";
import { MatAnchor, MatButton, MatIconButton } from "@angular/material/button";
import { MatFormField, MatLabel } from "@angular/material/form-field";
import { MatInput } from "@angular/material/input";
import { CartService } from '../../../Core/services/cart.service';
import { CurrencyPipe, Location, NgIf } from "@angular/common";
import { firstValueFrom } from 'rxjs';
import { StripeService } from '../../../Core/services/stripe.service';
import { MatIcon } from "@angular/material/icon";
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-order-summary',
  imports: [RouterLink, MatAnchor, MatButton, MatFormField, MatLabel, MatInput, CurrencyPipe, MatIconButton, MatIcon, FormsModule],
  templateUrl: './order-summary.component.html',
  styleUrl: './order-summary.component.scss',
})
export class OrderSummaryComponent {
  cartService = inject(CartService);
  private stripeService = inject(StripeService)
  location = inject(Location);
  code?: string;

  applyCoupon(){
    if(!this.code) return;
    this.cartService.applyDiscount(this.code).subscribe({
      next: async coupon => {
        const cart = this.cartService.cart();
        if(cart){
          cart.coupon = coupon;
          await firstValueFrom(this.cartService.setCart(cart));
          this.code = undefined;
        }
        if(this.location.path() === '/checkout'){
          await firstValueFrom(this.stripeService.createOrUpdatePaymentIntent());
        }
      }
    })
  }

  async removeCoupon(){
    const cart = this.cartService.cart();
    if(!cart) return;
    if(cart.coupon) cart.coupon = undefined;
    await firstValueFrom(this.cartService.setCart(cart));
    if(this.location.path() === '/checkout'){
      await firstValueFrom(this.stripeService.createOrUpdatePaymentIntent());
    }
  }
  
}
