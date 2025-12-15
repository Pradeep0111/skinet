import { Component, inject, OnInit } from '@angular/core';
import { ShopService } from '../../Core/services/shop.service';
import { Product } from '../../shared/models/product';
import { ProductItemComponent } from './product-item/product-item.component';

@Component({
  selector: 'app-shop',
  imports: [ProductItemComponent],
  templateUrl: './shop.component.html',
  styleUrl: './shop.component.scss',
})
export class ShopComponent implements OnInit {
  private shop = inject(ShopService);
  products: Product[] = [];



  ngOnInit(): void {
    this.shop.getProducts().subscribe({
      next: response => this.products = response.data,
      error: error => console.log(error)
    })
  }

}
