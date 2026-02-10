import { Component } from '@angular/core';
import { MatButton } from "@angular/material/button";
import { RouterLink } from "@angular/router";
import { DatePipe } from "@angular/common";

@Component({
  selector: 'app-checkout-success',
  imports: [MatButton, RouterLink, DatePipe],
  templateUrl: './checkout-success.component.html',
  styleUrl: './checkout-success.component.scss',
})
export class CheckoutSuccessComponent {
  today = new Date();
  randomNumber = Math.floor(Math.random() * 1000);
}
