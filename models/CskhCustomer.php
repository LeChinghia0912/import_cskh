<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class CskhCustomer extends Model
{
    protected $connection = 'mysql4';

    protected $table = 'cskh_customers';

    protected $fillable = [
        'name',
        'email',
        'address',
        'province_id',
        'district_id',
        'ward_id',
        'birthday',
        'customer_type',
    ];

    protected $casts = [
        'birthday' => 'date',
        'province_id' => 'integer',
        'district_id' => 'integer',
        'ward_id' => 'integer',
    ];

    public function phones(): HasMany
    {
        return $this->hasMany(CskhCustomerPhone::class, 'customer_id');
    }

    public function tickets(): HasMany
    {
        return $this->hasMany(CskhTicket::class, 'customer_id');
    }
}
