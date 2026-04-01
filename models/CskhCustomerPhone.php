<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class CskhCustomerPhone extends Model
{
    protected $connection = 'mysql4';

    protected $table = 'cskh_customer_phones';

    public const UPDATED_AT = null;

    protected $fillable = [
        'customer_id',
        'phone',
        'phone_normalized',
        'is_primary',
    ];

    protected $casts = [
        'customer_id' => 'integer',
        'is_primary' => 'boolean',
    ];

    public function customer(): BelongsTo
    {
        return $this->belongsTo(CskhCustomer::class, 'customer_id');
    }
}
