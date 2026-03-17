import { Component, inject, OnInit } from '@angular/core';
import { OrderService } from '../../../Core/services/order.service';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Order } from '../../../shared/models/order';
import { MatCard } from "@angular/material/card";
import { DatePipe, CurrencyPipe } from "@angular/common";
import { AddressPipe } from "../../../shared/pipes/address-pipe";
import { PaymentPipe } from "../../../shared/pipes/payment-pipe";
import { MatAnchor } from "@angular/material/button";

@Component({
  selector: 'app-order-detailed',
  imports: [MatCard, DatePipe, CurrencyPipe, AddressPipe, PaymentPipe, MatAnchor, RouterLink],
  templateUrl: './order-detailed.component.html',
  styleUrl: './order-detailed.component.scss',
})
export class OrderDetailedComponent implements OnInit{
  private orderService = inject(OrderService);
  private activatedRoute = inject(ActivatedRoute);
  order?: Order

  ngOnInit(): void {
    this.loadOrder();
  }

  loadOrder() {
    const id = this.activatedRoute.snapshot.paramMap.get('id');
    if(!id) return;
    this.orderService.getOrdersDetailed(+id).subscribe({
      next: order => this.order = order
    })
  }
}
