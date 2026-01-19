import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AccountService } from '../../../Core/services/account.service';
import { Router } from '@angular/router';
import { SnackbarService } from '../../../Core/services/snackbar.service';
import { MatCard } from "@angular/material/card";
import { MatFormField, MatLabel, MatError } from "@angular/material/form-field";
import { MatButton } from "@angular/material/button";
import { MatInput } from "@angular/material/input";
import { JsonPipe } from "@angular/common";
import { TextInputComponent } from "../../../shared/components/text-input/text-input.component";

@Component({
  selector: 'app-register',
  imports: [MatCard, ReactiveFormsModule, MatFormField, MatLabel, MatButton, MatInput, JsonPipe, MatError, TextInputComponent],
  templateUrl: './register.component.html',
  styleUrl: './register.component.scss',
})
export class RegisterComponent {
  private fb = inject(FormBuilder)
  private accountService = inject(AccountService)
  private router = inject(Router);
  private snack = inject(SnackbarService)
  validationErrors?: string[];

  registerForm = this.fb.group(
    {
      firstName : ['', Validators.required],
      lastName : ['' ,Validators.required],
      email : ['',[Validators.required, Validators.email]],
      password : ['', Validators.required]
    }
  )

  onSubmit(){
    this.accountService.register(this.registerForm.value).subscribe({
      next: () => {
        this.snack.success('Registeration successful - you can now login');
        this.router.navigateByUrl('/account/login')
      },
      error: errors => this.validationErrors = errors
    })
  }
}
