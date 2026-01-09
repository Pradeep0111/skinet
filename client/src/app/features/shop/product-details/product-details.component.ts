import { Component, inject, OnInit } from '@angular/core';
import { ShopService } from '../../../Core/services/shop.service';
import { ActivatedRoute } from '@angular/router';
import { Product } from '../../../shared/models/product';
import { CurrencyPipe, NgPlural } from "@angular/common";
import { MatAnchor } from "@angular/material/button";
import { MatIcon } from "@angular/material/icon";
import { MatFormField, MatFormFieldModule, MatLabel } from "@angular/material/form-field";
import { MatDivider } from "@angular/material/divider";
import { MatInputModule } from '@angular/material/input';
import { CartService } from '../../../Core/services/cart.service';
import { FormsModule } from "@angular/forms";

@Component({
  selector: 'app-product-detail',
  imports: [CurrencyPipe, MatAnchor, MatIcon, MatFormFieldModule, MatLabel, MatDivider, MatInputModule,FormsModule],
  templateUrl: './product-details.component.html',
  styleUrl: './product-details.component.scss',
})
export class ProductDetailsComponent implements OnInit{
  private shopService = inject(ShopService);
  private activatedRoute = inject(ActivatedRoute)
  private cartService = inject(CartService)
  product? : Product;
  quantityInCart = 0;
  quantity = 1;

  ngOnInit(): void {
    this.loadProduct();
  }
  loadProduct(){
    const id = this.activatedRoute.snapshot.paramMap.get('id');
    if(!id) return;
    this.shopService.getProduct(+id).subscribe({
      next: product => {
        this.product = product,
        this.updateQuantityInCart();
      },
      error: error => console.log(error)
    })
  }

  updateCart(){
    if(!this.product) return;
    if(this.quantity > this.quantityInCart){
      const itemsToAdd = this.quantity - this.quantityInCart;
      this.quantityInCart += itemsToAdd;
      this.cartService.addItemToCart(this.product, itemsToAdd);
    }else{
      const itemsToRemove = this.quantityInCart - this.quantity;
      this.quantityInCart -= itemsToRemove;
      this.cartService.removeItemFromCart(this.product.id, itemsToRemove);
    }
  }

  updateQuantityInCart(){
    this.quantityInCart = this.cartService.cart()?.items
      .find(x => x.productId === this.product?.id)?.quantity || 0;
    this.quantity = this.quantityInCart || 1;
  }

  getButtonText(){
    return this.quantityInCart > 0 ? "Update Cart" : "Add to Cart";
  }
}
