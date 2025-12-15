import { Component, inject, OnInit} from '@angular/core';
import { HeaderComponent } from "./layout/header/header.component";
import { HttpClient } from '@angular/common/http';
import { Product } from './shared/models/product';
import { Pagination } from './shared/models/pagination';
import { ShopService } from './Core/services/shop.service';
import { RouterOutlet } from '@angular/router';
import { ShopComponent } from "./features/shop/shop.component";

@Component({
  selector: 'app-root',
  imports: [HeaderComponent, ShopComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent{
  // baseUrl = 'https://localhost:5000/api/';
  // private http = inject(HttpClient);
  // products: any[] = []
  // ngOnInit(): void {
  //   this.shop.getProducts().subscribe({
  //   next: response => {
  //     console.log('API response:', response);
  //     this.products = response.data;
  //     console.log('Products array:', this.products);
  //   },
  //   error: error => console.error('API error:', error)
  // });
  // }
  // private shop = inject(ShopService)
  title = 'Skinet';
  // products: Product[] = [];



  // ngOnInit(): void {
  //   this.shop.getProducts().subscribe({
  //     next: response => this.products = response.data,
  //   //   next: response => {
  //   //   console.log('Products received:', response);
  //   //   this.products = response.data;
  //   // },
  //     error: error => console.log(error)
  //   })
  // }
}
