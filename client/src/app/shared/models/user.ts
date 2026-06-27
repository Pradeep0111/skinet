export type User ={
    firstName: string;
    lastName : string;
    email : string;
    address : Address;
    roles : string | string[];
}

export type Address = {
    line1: string;
    line2?: string;
    city: string;
    country: string;
    state: string;
    postalCode: string;
}