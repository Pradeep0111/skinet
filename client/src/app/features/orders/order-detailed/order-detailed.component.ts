import { Component, inject, OnInit } from '@angular/core';
import { OrderService } from '../../../Core/services/order.service';
import { ActivatedRoute, Router } from '@angular/router';
import { Order } from '../../../shared/models/order';
import { MatCard } from "@angular/material/card";
import { DatePipe, CurrencyPipe } from "@angular/common";
import { AddressPipe } from "../../../shared/pipes/address-pipe";
import { PaymentPipe } from "../../../shared/pipes/payment-pipe";
import { MatAnchor } from "@angular/material/button";
import { AccountService } from '../../../Core/services/account.service';
import { AdminService } from '../../../Core/services/admin.service';

@Component({
  selector: 'app-order-detailed',
  imports: [MatCard, DatePipe, CurrencyPipe, AddressPipe, PaymentPipe, MatAnchor],
  templateUrl: './order-detailed.component.html',
  styleUrl: './order-detailed.component.scss',
})
export class OrderDetailedComponent implements OnInit{
  private orderService = inject(OrderService);
  private activatedRoute = inject(ActivatedRoute);
  private accountService = inject(AccountService);
  private adminService = inject(AdminService);
  private router = inject(Router);
  order?: Order
  buttonText = this.accountService.isAdmin() ? 'Return to Admin' : 'Return to Orders'


  ngOnInit(): void {
    this.loadOrder();
  }

  onReturnClick() {
      if(this.accountService.isAdmin()) {
        this.router.navigate(['/admin']);
      } else {
        this.router.navigate(['/orders']);
      }
    }

  loadOrder() {
    const id = this.activatedRoute.snapshot.paramMap.get('id');
    if(!id) return;

    const loadOrderData = this.accountService.isAdmin()?
      this.adminService.getOrder(+id) : 
      this.orderService.getOrdersDetailed(+id)

    loadOrderData.subscribe({
      next: order => this.order = order
    })
  }
}
