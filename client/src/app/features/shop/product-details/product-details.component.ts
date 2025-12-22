import { Component, inject, OnInit } from '@angular/core';
import { ShopService } from '../../../Core/services/shop.service';
import { ActivatedRoute } from '@angular/router';
import { Product } from '../../../shared/models/product';
import { CurrencyPipe } from "@angular/common";
import { MatAnchor } from "@angular/material/button";
import { MatIcon } from "@angular/material/icon";
import { MatFormField, MatFormFieldModule, MatLabel } from "@angular/material/form-field";
import { MatDivider } from "@angular/material/divider";
import { MatInputModule } from '@angular/material/input';

@Component({
  selector: 'app-product-detail',
  imports: [CurrencyPipe, MatAnchor, MatIcon, MatFormFieldModule, MatLabel, MatDivider, MatInputModule],
  templateUrl: './product-details.component.html',
  styleUrl: './product-details.component.scss',
})
export class ProductDetailsComponent implements OnInit{
  private shopService = inject(ShopService);
  private activatedRoute = inject(ActivatedRoute)
  product? : Product;
  ngOnInit(): void {
    this.loadProduct();
  }
  loadProduct(){
    const id = this.activatedRoute.snapshot.paramMap.get('id');
    if(!id) return;
    this.shopService.getProduct(+id).subscribe({
      next: product => this.product = product,
      error: error => console.log(error)
    })
  }
}
