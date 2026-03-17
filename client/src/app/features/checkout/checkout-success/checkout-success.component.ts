import { Component, inject, OnDestroy } from '@angular/core';
import { MatButton } from "@angular/material/button";
import { RouterLink } from "@angular/router";
import { CurrencyPipe, DatePipe } from "@angular/common";
import { SignalrService } from '../../../Core/services/signalr.service';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { PaymentPipe } from '../../../shared/pipes/payment-pipe';
import { AddressPipe } from '../../../shared/pipes/address-pipe';
import { OrderService } from '../../../Core/services/order.service';

@Component({
  selector: 'app-checkout-success',
  imports: [MatButton, RouterLink, DatePipe, MatProgressSpinnerModule, PaymentPipe, AddressPipe, CurrencyPipe],
  templateUrl: './checkout-success.component.html',
  styleUrl: './checkout-success.component.scss',
})
export class CheckoutSuccessComponent implements OnDestroy{
  signalrService = inject(SignalrService);
  private orderService = inject(OrderService);

  ngOnDestroy(): void {
    this.orderService.orderComplete = false;
    this.signalrService.orderSignal.set(null);
  }  
}
