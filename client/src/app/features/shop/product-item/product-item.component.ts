import { Component, Input } from '@angular/core';
import { Product } from '../../../shared/models/product';
import { MatCard } from "@angular/material/card";

@Component({
  selector: 'app-product-item',
  imports: [MatCard],
  templateUrl: './product-item.component.html',
  styleUrl: './product-item.component.scss',
})
export class ProductItemComponent {
  @Input() product?: Product;
}
