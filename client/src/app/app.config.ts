import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners, provideZoneChangeDetection} from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { errorInterceptor } from './Core/interceptor/error-interceptor';
import { loadingInterceptor } from './Core/interceptor/loading-interceptor';
import { InitService } from './Core/services/init.service';
import { lastValueFrom } from 'rxjs';
import { authInterceptor } from './Core/interceptor/auth-interceptor';


export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([errorInterceptor, loadingInterceptor, authInterceptor])),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideAppInitializer( async () => {
      const initService = inject(InitService);
      return lastValueFrom(initService.init()).finally(() =>{
        const splash = document.getElementById('initial-splash');
        if(splash){
          splash.remove();
        }
      })
    })
  ]
};
